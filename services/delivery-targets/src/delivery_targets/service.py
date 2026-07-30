"""The Delivery Targets service pipeline (design §4 / §9).

load catalog -> one adapter selection -> §9 validation -> store artifacts ->
§3 response. There is exactly one model attempt (FR-DT-14); repair-retry is
not implemented. A validated selection is stored as a successful artifact; an
invalid one is stored as a failed artifact with its errors, and the response
reports ``failed`` (FR-DT-21). Invalid output is never silently rescued.
"""

from __future__ import annotations

import logging
from typing import Any

from .artifact_store import ArtifactStore
from .catalog_store import CatalogStore
from .contracts import (
    SelectionArtifact,
    SelectionRequest,
    SelectionResponse,
)
from .llm_adapter import LLMAdapter
from .screen import Finding, screen_for_injection
from .validators import validate_selection

logger = logging.getLogger(__name__)


class SelectionService:
    def __init__(
        self,
        *,
        settings: Any,
        adapter: LLMAdapter,
        catalog_store: CatalogStore,
        artifact_store: ArtifactStore,
    ) -> None:
        self._settings = settings
        self._adapter = adapter
        self._catalog_store = catalog_store
        self._artifact_store = artifact_store

    def select(self, request: SelectionRequest) -> SelectionResponse:
        catalog = self._catalog_store.load_targets()
        catalog_target_ids = {entry["delivery_target"] for entry in catalog}

        # FR-DT-24 / ADR-0021: screen learner free-text for prompt injection before
        # it reaches any adapter. Runs adapter-independently so replay is screened
        # too; POC posture is flag-and-record (in the audit log), not block.
        findings = screen_for_injection(request.learner_context)
        if findings:
            logger.warning(
                "prompt-injection screen flagged learner_context paths: %s",
                [f.path for f in findings],
            )

        # Exactly one attempt (FR-DT-14); no hidden repair retry.
        generation, meta = self._adapter.select(request, catalog=catalog)
        logger.info(
            "selection generated: execution_id=%s event_id=%s event_type=%s provider=%s "
            "proposed_targets=%s",
            request.execution_id, request.event_id, request.event_type, meta.provider,
            [sel.delivery_target for sel in generation.selections],
        )
        errors = validate_selection(generation, catalog_target_ids=catalog_target_ids)
        logger.info(
            "validation decision: execution_id=%s event_id=%s status=%s errors=%s",
            request.execution_id, request.event_id,
            "failed" if errors else "succeeded", errors,
        )

        log_ref = self._artifact_store.store_invocation_log(
            _invocation_log(request, generation, meta, errors, findings),
            key=request.execution_id,
        )

        if errors:
            self._artifact_store.store_failed(
                request.execution_id, "; ".join(errors)
            )
            logger.info(
                "failed artifact stored: execution_id=%s event_id=%s log_ref=%s",
                request.execution_id, request.event_id, log_ref,
            )
            return SelectionResponse.failed(llm_invocation_log_ref=log_ref)

        artifact = SelectionArtifact(
            execution_id=request.execution_id,
            event_type=request.event_type,
            source_system=request.source_system,
            selections=generation.selections,
        )
        selection_ref = self._artifact_store.store_selection(artifact)
        logger.info(
            "selection stored: execution_id=%s event_id=%s selected_targets=%s "
            "selection_ref=%s log_ref=%s",
            request.execution_id, request.event_id,
            [sel.delivery_target for sel in generation.selections], selection_ref, log_ref,
        )
        return SelectionResponse.succeeded(
            selection_artifact_ref=selection_ref,
            # The rich per-target list (§3): confidence + rationale inline so the
            # Orchestrator needs no second round-trip to the stored artifact.
            selected_targets=generation.selections,
            llm_invocation_log_ref=log_ref,
        )


def _invocation_log(
    request: SelectionRequest,
    generation: Any,
    meta: Any,
    errors: list[str],
    injection_findings: list[Finding],
) -> dict[str, Any]:
    # ADR-0010 §60: capture per-invocation model metadata (model/provider/temperature/
    # tokens/latency) plus the prompt sent and the structured output, so the audit
    # trail shows exactly what the model received and returned.
    return {
        "status": "failed" if errors else "succeeded",
        "service": "delivery-targets",
        "phase": "delivery_targets",
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "event_type": request.event_type,
        "source_system": request.source_system,
        "provider": meta.provider,
        "model_id": meta.model_id,
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "selections": [sel.model_dump() for sel in generation.selections],
        "selected_targets": [sel.delivery_target for sel in generation.selections],
        "validation_errors": errors,
        "injection_findings": [
            {"path": f.path, "snippet": f.snippet} for f in injection_findings
        ],
        "corpus_scenario_id": None,
    }
