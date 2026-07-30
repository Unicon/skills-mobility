"""Request/response contracts for the Delivery Targets LLM Decision Service.

Design refs: §6 (transient-context-first request) and §3 (compact response
envelope). The response carries the flat selected_targets list the delivery-phase
Workflow Actions call needs directly, plus refs to the stored artifacts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict


class DeliveryTarget(StrEnum):
    """POC delivery targets (ADR-0016)."""

    LEARNCARD_ISSUER = "learncard_issuer"
    LEARNCARD_WALLET = "learncard_wallet"
    SMART_RESUME = "smart_resume"


class SelectionRequest(BaseModel):
    """§6 request. Context is passed inline by default (ADR-0007). The example
    surfaces in Swagger's "Try it out" panel; ``course_id`` is what replay mode
    resolves the course subject from (``ACCY-*`` vs ``FINC-*``)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "execution_id": "exec_1",
                "event_id": "evt_1",
                "event_type": "skill_mastered",
                "source_system": "mock_lms",
                "learner_context": {
                    "learner_id": "learner_42",
                    "course_id": "ACCY-111",
                    "recipient_profile_id": "smi-demo-learner",
                },
            }
        },
    )

    execution_id: str
    event_id: str
    event_type: str
    source_system: str
    learner_context: dict[str, Any]


class TargetSelection(BaseModel):
    """One selected target with its confidence and rationale."""

    model_config = ConfigDict(extra="forbid")

    delivery_target: str
    confidence: float
    rationale: str


class SelectionResponse(BaseModel):
    """§3 response envelope. Build via succeeded / failed so the contract
    remains self-enforcing. ``selected_targets`` is the rich per-target list
    (delivery_target + confidence + rationale) so the Orchestrator reads the
    decision directly — no second round-trip to the stored artifact (§3)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    selection_artifact_ref: str | None
    selected_targets: list[TargetSelection]
    llm_invocation_log_ref: str | None

    @classmethod
    def succeeded(
        cls,
        *,
        selection_artifact_ref: str,
        selected_targets: list[TargetSelection],
        llm_invocation_log_ref: str,
    ) -> Self:
        return cls(
            status="succeeded",
            selection_artifact_ref=selection_artifact_ref,
            selected_targets=selected_targets,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )

    @classmethod
    def failed(cls, *, llm_invocation_log_ref: str | None = None) -> Self:
        return cls(
            status="failed",
            selection_artifact_ref=None,
            selected_targets=[],
            llm_invocation_log_ref=llm_invocation_log_ref,
        )


# --- Structured model output ---



class SelectionGeneration(BaseModel):
    """The structured model output the LLM/replay adapter returns (§7): the list
    of selected targets each with confidence and rationale."""

    model_config = ConfigDict(extra="forbid")

    selections: list[TargetSelection]


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


# --- Stored artifacts ---


class SelectionArtifact(BaseModel):
    """§2 stored selection artifact: the routing decision for one workflow
    execution, with per-target confidence and rationale."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    execution_id: str
    event_type: str
    source_system: str
    selections: list[TargetSelection]
