"""The Field Synthesis service pipeline (design §3 / §10).

resolve briefs -> screen -> one adapter generation -> §10 validation -> store artifacts ->
§9 response. There is exactly one model attempt (FR-FS-14); repair-retry is not
implemented. A validated generation is stored as a successful artifact; an invalid
one is stored as a failed artifact with its errors, and the response reports ``failed``
(FR-FS-10). Invalid output is never silently rescued.
"""

from __future__ import annotations

from typing import Any

from .artifact_store import ArtifactStore
from .contracts import (
    SynthesisRequest,
    SynthesisRequestArtifact,
    SynthesisResponse,
    SynthesisResultArtifact,
)
from .llm_adapter import LLMAdapter
from .validators import validate_generation


class SynthesisService:
    def __init__(
        self,
        *,
        settings: Any,
        adapter: LLMAdapter,
        artifact_store: ArtifactStore,
    ) -> None:
        self._settings = settings
        self._adapter = adapter
        self._artifact_store = artifact_store

    def synthesize(self, request: SynthesisRequest) -> SynthesisResponse:
        # Resolve the synthesis-request artifact: inline takes precedence; otherwise
        # load by ref from the artifact store.
        synthesis_artifact = self._resolve_synthesis_request(request)
        briefs = synthesis_artifact.requests
        requested_ids = {b.placeholder_id for b in briefs}

        # Exactly one attempt (FR-FS-14); no hidden repair retry.
        generation, meta = self._adapter.generate(request, briefs=briefs)
        errors = validate_generation(generation, requested_ids=requested_ids)

        log_ref = self._artifact_store.store_invocation_log(
            _invocation_log(request, generation, meta, errors),
            key=request.execution_id,
        )

        if errors:
            self._artifact_store.store_failed(
                request.execution_id, "; ".join(errors)
            )
            return SynthesisResponse.failed(llm_invocation_log_ref=log_ref)

        artifact = SynthesisResultArtifact(
            transformation_type=request.transformation_type,
            execution_id=request.execution_id,
            values=generation.values,
            confidence=generation.confidence,
            rationale=generation.rationale,
        )
        result_ref = self._artifact_store.store_synthesis_result(artifact)
        return SynthesisResponse.succeeded(
            synthesis_result_ref=result_ref,
            llm_invocation_log_ref=log_ref,
        )

    def _resolve_synthesis_request(
        self, request: SynthesisRequest
    ) -> SynthesisRequestArtifact:
        if request.synthesis_request is not None:
            return request.synthesis_request
        if request.synthesis_request_ref is not None:
            return self._artifact_store.load_synthesis_request(request.synthesis_request_ref)
        raise ValueError(
            "SynthesisRequest must supply either synthesis_request or synthesis_request_ref"
        )


def _invocation_log(
    request: SynthesisRequest,
    generation: Any,
    meta: Any,
    errors: list[str],
) -> dict[str, Any]:
    # ADR-0010 §60: capture per-invocation model metadata (model/provider/temperature/
    # tokens/latency) plus the prompt sent and the structured output, so the audit
    # trail shows exactly what the model received and returned.
    return {
        "status": "failed" if errors else "succeeded",
        "service": "field-synthesis",
        "phase": request.transformation_type,
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "transformation_type": request.transformation_type,
        "provider": meta.provider,
        "model_id": meta.model_id,
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "values": generation.values,
        "confidence": generation.confidence,
        "rationale": generation.rationale,
        "validation_errors": errors,
        "corpus_scenario_id": None,
    }
