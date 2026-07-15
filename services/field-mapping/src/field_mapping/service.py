"""The Field Mapping service pipeline (design §9 / §11).

resolve catalogs -> one adapter generation -> §11 validation -> store artifacts
-> §10 response. There is exactly one model attempt (FR-FM-18); repair-retry (§12)
is a config flag, off by default and not implemented. A validated generation is
stored as a successful mapping; an invalid one is stored as a failed artifact with
its errors, and the response reports ``failed`` (§11). Invalid output is never
silently rescued.
"""

from __future__ import annotations

from typing import Any

from .artifact_loader import load_source_payloads
from .artifact_store import ArtifactStore, FailedArtifactError, stable_key
from .catalog_store import CatalogStore
from .contracts import (
    LlmCallMeta,
    MappingArtifact,
    MappingGeneration,
    MappingRequest,
    MappingResponse,
    SynthesisRequestArtifact,
    TransformationType,
)
from .llm_adapter import LLMAdapter
from .validators import validate_generation


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
        target_schema = self._catalogs.resolve_target(
            transformation_type=request.transformation_type,
            delivery_target=request.delivery_target,
        )
        # The fetch-profile required-alias gate applies to the raw-LMS credential_template
        # phase; issuer/wallet phases consume upstream transformation output (the exact
        # source_payloads keys are the open orchestrator seam item, PR #33).
        required = self._required_aliases(request)
        load_source_payloads(request, required_aliases=required)

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
        generation, meta = self._adapter.generate(request, target_schema=target_schema)
        errors = validate_generation(generation, request=request, target_schema=target_schema)
        log_ref = self._artifacts.store_invocation_log(
            _invocation_log(request, generation, meta, errors), key=key
        )

        if errors:
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
        if generation.placeholder_ids:
            synthesis_ref = self._artifacts.store_synthesis_request(
                SynthesisRequestArtifact(
                    transformation_type=request.transformation_type,
                    requests=generation.synthesis_requests,
                ),
                key=key,
            )
        return MappingResponse.succeeded(
            mapping_artifact_ref=mapping_ref,
            synthesis_request_ref=synthesis_ref,
            llm_invocation_log_ref=log_ref,
            synthesis_allowed=request.synthesis_allowed,
            placeholder_ids=generation.placeholder_ids,
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
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "jsonata": generation.jsonata,
        "placeholder_ids": generation.placeholder_ids,
        "confidence": generation.confidence,
        "rationale": generation.rationale,
        "validation_errors": errors,
        "corpus_scenario_id": None,
    }
