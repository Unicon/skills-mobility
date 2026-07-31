"""The Field Mapping service pipeline (design §9 / §11).

resolve catalogs -> one adapter generation -> §11 validation -> store artifacts
-> §10 response. There is exactly one model attempt (FR-FM-18); repair-retry (§12)
is a config flag, off by default and not implemented. A validated generation is
stored as a successful mapping; an invalid one is stored as a failed artifact with
its errors, and the response reports ``failed`` (§11). Invalid output is never
silently rescued.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .artifact_loader import load_source_payloads
from .artifact_store import ArtifactStore, FailedArtifactError, stable_key
from .catalog_store import CatalogNotFoundError, CatalogStore
from .contracts import (
    LlmCallMeta,
    MappingArtifact,
    MappingGeneration,
    MappingRequest,
    MappingResponse,
    SynthesisRequestArtifact,
    SynthesisRequestEntry,
    TransformationType,
)
from .llm_adapter import LLMAdapter
from .validators import validate_generation

logger = logging.getLogger(__name__)


class MappingService:
    def __init__(
        self,
        *,
        catalog_store: CatalogStore,
        artifact_store: ArtifactStore,
        adapter: LLMAdapter,
        reuse_stored: bool = False,
        repair_retry: bool = False,
    ) -> None:
        self._catalogs = catalog_store
        self._artifacts = artifact_store
        self._adapter = adapter
        self._reuse_stored = reuse_stored
        self._repair_retry = repair_retry

    def map(self, request: MappingRequest) -> MappingResponse:
        logger.info(
            "mapping request received: execution_id=%s event_id=%s "
            "transformation_type=%s delivery_target=%s",
            request.execution_id,
            request.event_id,
            request.transformation_type,
            request.delivery_target,
        )
        target_schema = self._catalogs.resolve_target(
            transformation_type=request.transformation_type,
            delivery_target=request.delivery_target,
        )
        # The fetch-profile required-alias gate applies to the raw-LMS credential_template
        # phase; issuer/wallet phases consume upstream transformation output (the exact
        # source_payloads keys are the open orchestrator seam item, PR #33).
        required = self._required_aliases(request)
        load_source_payloads(request, required_aliases=required)

        # Design §7: resolve source-field catalog for each top-level key present in
        # source_payloads; skip keys with no catalog (best-effort, never fail the request).
        source_catalogs: dict[str, dict[str, Any]] = {}
        for alias in request.source_payloads:
            try:
                source_catalogs[alias] = self._catalogs.resolve_source_catalog(
                    source_system=request.source_system, resource_schema_id=alias
                )
            except CatalogNotFoundError:
                pass

        key = stable_key(
            source_system=request.source_system,
            fetch_profile_id=request.fetch_profile_id,
            transformation_type=request.transformation_type,
            delivery_target=request.delivery_target,
        )

        # §13: reuse a stored mapping only when explicitly enabled (default off).
        if self._reuse_stored:
            reused = self._reuse(key, request)
            if reused is not None:
                return reused

        # Exactly one attempt (FR-FM-18); repair-retry is not implemented.
        generation, meta = self._adapter.generate(
            request, target_schema=target_schema, source_catalogs=source_catalogs or None
        )
        errors = validate_generation(generation, request=request, target_schema=target_schema)
        log_ref = self._artifacts.store_invocation_log(
            _invocation_log(request, generation, meta, errors), key=key
        )

        if errors:
            logger.info(
                "mapping failed: execution_id=%s validation_error_count=%d",
                request.execution_id,
                len(errors),
            )
            self._artifacts.store_failed_mapping(
                source_system=request.source_system,
                fetch_profile_id=request.fetch_profile_id,
                transformation_type=request.transformation_type,
                delivery_target=request.delivery_target,
                validation_errors=errors,
            )
            return MappingResponse.failed(llm_invocation_log_ref=log_ref)

        mapping_ref = self._artifacts.store_mapping(
            MappingArtifact(
                transformation_type=request.transformation_type,
                source_system=request.source_system,
                fetch_profile_id=request.fetch_profile_id,
                delivery_target=request.delivery_target,
                target_schema_ref=f"schema:{request.transformation_type}:v1",
                jsonata=generation.jsonata,
                placeholder_ids=generation.placeholder_ids,
            )
        )
        synthesis_ref: str | None = None
        synthesis_artifact: SynthesisRequestArtifact | None = None
        if generation.placeholder_ids:
            synthesis_artifact = SynthesisRequestArtifact(
                transformation_type=request.transformation_type,
                requests=_ground_synthesis_briefs(
                    generation.synthesis_requests, request.source_payloads
                ),
            )
            synthesis_ref = self._artifacts.store_synthesis_request(synthesis_artifact, key=key)
        logger.info(
            "mapping succeeded: execution_id=%s requires_synthesis=%s",
            request.execution_id,
            bool(generation.placeholder_ids),
        )
        return MappingResponse.succeeded(
            mapping_artifact_ref=mapping_ref,
            synthesis_request_ref=synthesis_ref,
            llm_invocation_log_ref=log_ref,
            synthesis_allowed=request.synthesis_allowed,
            placeholder_ids=generation.placeholder_ids,
            mapping=generation.jsonata,
            target_schema=target_schema,
            # exclude_none so the inline artifact matches the Field Synthesis brief
            # schema (its source_payloads/paths default to empty, not null).
            synthesis_request=(
                synthesis_artifact.model_dump(exclude_none=True) if synthesis_artifact else None
            ),
        )

    def _required_aliases(self, request: MappingRequest) -> list[str]:
        if request.transformation_type is not TransformationType.CREDENTIAL_TEMPLATE:
            return []
        profile = self._catalogs.resolve_fetch_profile(
            source_system=request.source_system, fetch_profile_id=request.fetch_profile_id
        )
        aliases: list[str] = profile.get("required_aliases", [])
        return aliases

    def _reuse(self, key: str, request: MappingRequest) -> MappingResponse | None:
        try:
            artifact = self._artifacts.load_mapping(f"mapping:{key}")
        except (FileNotFoundError, FailedArtifactError):
            return None
        synthesis_ref = f"synthesis:{key}" if artifact.placeholder_ids else None
        return MappingResponse.succeeded(
            mapping_artifact_ref=f"mapping:{key}",
            synthesis_request_ref=synthesis_ref,
            llm_invocation_log_ref=f"llmcall:{key}",
            synthesis_allowed=request.synthesis_allowed,
            placeholder_ids=artifact.placeholder_ids,
        )


_LEADING_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)")


def _referenced_top_level_keys(paths: list[str]) -> list[str]:
    """The distinct top-level source keys the paths name (e.g. ``course.name`` and
    ``pages[?id='x'].body`` -> ``course``, ``pages``). Tolerant of the ad-hoc path
    syntax the LLM emits — we only need the leading segment, not full-path eval."""
    keys: list[str] = []
    for path in paths:
        segment = path.removeprefix("source_payloads.")
        match = _LEADING_KEY.match(segment)
        if match:
            key = match.group(1)
            if key != "source_payloads" and key not in keys:
                keys.append(key)
    return keys


def _ground_synthesis_briefs(
    requests: list[SynthesisRequestEntry], source_payloads: dict[str, Any]
) -> list[SynthesisRequestEntry]:
    """Make each synthesis brief self-contained for the (separate-store) Field
    Synthesis service by populating its ``source_payloads`` snapshot from the source
    data this service already holds. When the LLM referenced only
    ``source_payload_paths``, snapshot the top-level source slices those paths name
    (full source_payloads if none resolve). Briefs that already carry a snapshot are
    left untouched (§2: a provided snapshot is authoritative)."""
    grounded: list[SynthesisRequestEntry] = []
    for brief in requests:
        if brief.source_payloads is not None:
            grounded.append(brief)
            continue
        keys = _referenced_top_level_keys(brief.source_payload_paths or [])
        snapshot = {k: source_payloads[k] for k in keys if k in source_payloads}
        if not snapshot:
            snapshot = dict(source_payloads)
        grounded.append(brief.model_copy(update={"source_payloads": snapshot}))
    return grounded


def _invocation_log(
    request: MappingRequest,
    generation: MappingGeneration,
    meta: LlmCallMeta,
    errors: list[str],
) -> dict[str, Any]:
    # ADR-0010 §60: capture per-invocation model metadata (model/provider/temperature/
    # tokens/latency) plus the prompt sent and the structured output, so the audit
    # trail shows exactly what the model received and returned.
    return {
        "status": "failed" if errors else "succeeded",
        "service": "field-mapping",
        "phase": str(request.transformation_type),
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "transformation_type": str(request.transformation_type),
        "delivery_target": str(request.delivery_target) if request.delivery_target else None,
        "source_system": request.source_system,
        "fetch_profile_id": request.fetch_profile_id,
        "provider": meta.provider,
        "model_id": meta.model_id,
        "prompt_template_version": meta.prompt_template_version,
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "injection_findings": meta.injection_findings,
        "jsonata": generation.jsonata,
        "placeholder_ids": generation.placeholder_ids,
        "confidence": generation.confidence,
        "rationale": generation.rationale,
        "validation_errors": errors,
        "corpus_scenario_id": None,
    }
