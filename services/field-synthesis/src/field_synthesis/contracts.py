"""Request/response contracts for the Field Synthesis LLM Decision Service.

Design refs: §4 (request contract), §2 (synthesis result artifact), §9 (response
contract). The response carries refs to the stored artifacts; the Orchestrator
passes ``synthesis_result_ref`` to the Transformation Executor which merges the
generated values under the ``synthesized`` namespace before running JSONata.
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict

# --- Synthesis brief and request artifact (Field Mapping's output → our input) ---


class SynthesisBrief(BaseModel):
    """One placeholder's synthesis task, produced by the Field Mapping service.

    At least one of ``source_payloads`` or ``source_payload_paths`` must be
    present per design §5; the service uses ``source_payloads`` as the concrete
    source material for generation.
    """

    model_config = ConfigDict(extra="forbid")

    placeholder_id: str
    target_path: str
    source_payload_paths: list[str] = []
    source_payloads: dict[str, Any] = {}
    instruction: str


class SynthesisRequestArtifact(BaseModel):
    """The synthesis-request artifact produced by Field Mapping and consumed here.

    Schema-versioned so coordinated changes across the two services remain
    traceable (design §16, FR-FS-17).
    """

    model_config = ConfigDict(extra="forbid")

    synthesis_request_schema_version: Literal["v1"] = "v1"
    transformation_type: str
    requests: list[SynthesisBrief]


# --- Service request ---


class SynthesisRequest(BaseModel):
    """§4 request. Context is passed inline by default (ADR-0007) or by ref for
    production-shaped orchestration flows (``synthesis_request_ref``)."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    event_id: str
    transformation_type: str
    # Either the synthesis-request artifact stored by Field Mapping (normal flow)
    # or the artifact inline (local dev / testing convenience).
    synthesis_request_ref: str | None = None
    synthesis_request: SynthesisRequestArtifact | None = None


# --- Structured model output ---


class SynthesisGeneration(BaseModel):
    """The structured model output the LLM/replay adapter returns (design §7):
    a flat map of generated text values keyed by ``placeholder_id``, plus
    generation-level confidence and rationale for the invocation log."""

    values: dict[str, str]
    confidence: float | None = None
    rationale: str | None = None


# --- Stored artifacts ---


class SynthesisResultArtifact(BaseModel):
    """§2 stored synthesis result artifact: the generated text for every
    requested placeholder in one transformation-loop invocation."""

    model_config = ConfigDict(extra="forbid")

    synthesis_result_schema_version: Literal["v1"] = "v1"
    transformation_type: str
    execution_id: str
    values: dict[str, str]
    confidence: float | None
    rationale: str | None


# --- Service response ---


class SynthesisResponse(BaseModel):
    """§9 compact response envelope. Build via ``succeeded`` / ``failed`` so the
    contract remains self-enforcing."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    synthesis_result_ref: str | None
    llm_invocation_log_ref: str | None

    @classmethod
    def succeeded(
        cls,
        *,
        synthesis_result_ref: str,
        llm_invocation_log_ref: str,
    ) -> Self:
        return cls(
            status="succeeded",
            synthesis_result_ref=synthesis_result_ref,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )

    @classmethod
    def failed(cls, *, llm_invocation_log_ref: str | None = None) -> Self:
        return cls(
            status="failed",
            synthesis_result_ref=None,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )


# --- Invocation metadata ---


class LlmCallMeta(BaseModel):
    """Per-invocation model-call metadata the adapter captures (ADR-0010 §60), so
    the invocation log can show exactly what the model received and returned.
    Replay mode uses sentinel values (provider ``replay``, no token/latency)."""

    provider: str
    model_id: str
    temperature: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None
    system_prompt: str | None = None
    user_prompt: str | None = None
