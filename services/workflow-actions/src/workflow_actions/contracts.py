"""Request/response contracts for the Workflow Actions LLM Decision Service.

Two stages, two entry-point pairs:
  Stage 1 — Pre-target gate: GateRequest / GateResponse
  Stage 2 — Delivery-phase plan: PlanRequest / PlanResponse

The stored plan artifact types (InputBinding, PlanStep, PlanApplicability,
PlanGenerator, DeliveryPhasePlan, GateDecision) are reproduced here from the
orchestrator schema so this service is self-contained; the shapes are kept
field-for-field identical to orchestrator.schemas (design §2).
"""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict

# ---------------------------------------------------------------------------
# Shared plan-artifact types (aligned to orchestrator.schemas field-for-field)
# ---------------------------------------------------------------------------

InputSource = Literal["workflow", "step", "literal"]
StepType = Literal["call", "wait", "for_each", "terminate"]


class InputBinding(BaseModel):
    """How the executor resolves one step input (orchestrator design §4)."""

    model_config = ConfigDict(extra="forbid")

    source: InputSource
    path: str | None = None  # source == "workflow": dotted path into workflow context
    step_id: int | None = None  # source == "step": prior step's full output
    value: Any = None  # source == "literal"


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: int
    type: StepType = "call"
    action_id: str
    inputs: dict[str, InputBinding] = {}
    produces: str | None = None


class PlanGenerator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_version: str
    model_identifier: str = "stub"
    prompt_template_version: str = ""


class PlanApplicability(BaseModel):
    """Reuse key for a stored delivery-phase plan (ADR-0011)."""

    model_config = ConfigDict(extra="forbid")

    event_type: str
    source_system: str = "mock_lms"
    selected_targets: list[str] = []


class DeliveryPhasePlan(BaseModel):
    """The reusable delivery-phase plan artifact the executor runs (ADR-0009 §2)."""

    model_config = ConfigDict(extra="forbid")

    plan_schema_version: str = "v1"
    plan_id: str
    generated_at: str = ""
    generator: PlanGenerator
    applicability: PlanApplicability
    confidence: float = 1.0
    rationale: str = ""
    steps: list[PlanStep] = []


class GateDecision(BaseModel):
    """Pre-target gate decision — execution-scoped, never stored for reuse (ADR-0009)."""

    model_config = ConfigDict(extra="forbid")

    decision: str  # "continue" or "terminate" (reason in rationale, FR-WA-2)
    confidence: float = 1.0
    rationale: str = ""


# ---------------------------------------------------------------------------
# Stage 1 — Pre-target gate
# ---------------------------------------------------------------------------


class GateRequest(BaseModel):
    """§5 gate request."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    event_id: str
    event_type: str
    event: dict[str, Any]
    context_bundle: dict[str, Any]
    policy_context: dict[str, Any] | None = None


class GateResponse(BaseModel):
    """§4 gate response envelope."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    decision: str | None
    confidence: float | None
    rationale: str | None
    llm_invocation_log_ref: str | None

    @classmethod
    def succeeded(
        cls,
        *,
        decision: str,
        confidence: float,
        rationale: str,
        llm_invocation_log_ref: str,
    ) -> Self:
        return cls(
            status="succeeded",
            decision=decision,
            confidence=confidence,
            rationale=rationale,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )

    @classmethod
    def failed(cls, *, llm_invocation_log_ref: str | None = None) -> Self:
        return cls(
            status="failed",
            decision=None,
            confidence=None,
            rationale=None,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )


class GateGeneration(BaseModel):
    """The structured model output for the gate stage."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    confidence: float
    rationale: str


# ---------------------------------------------------------------------------
# Stage 2 — Delivery-phase plan
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    """§5 delivery-phase plan request."""

    model_config = ConfigDict(extra="forbid")

    execution_id: str
    event_id: str
    event_type: str
    source_system: str
    event: dict[str, Any]
    context_bundle: dict[str, Any]
    selected_targets: list[str]


class PlanResponse(BaseModel):
    """§4 delivery-phase plan response envelope."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed"]
    plan: DeliveryPhasePlan | None
    plan_ref: str | None
    confidence: float | None
    rationale: str | None
    llm_invocation_log_ref: str | None

    @classmethod
    def succeeded(
        cls,
        *,
        plan: DeliveryPhasePlan,
        plan_ref: str,
        confidence: float,
        rationale: str,
        llm_invocation_log_ref: str,
    ) -> Self:
        return cls(
            status="succeeded",
            plan=plan,
            plan_ref=plan_ref,
            confidence=confidence,
            rationale=rationale,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )

    @classmethod
    def failed(cls, *, llm_invocation_log_ref: str | None = None) -> Self:
        return cls(
            status="failed",
            plan=None,
            plan_ref=None,
            confidence=None,
            rationale=None,
            llm_invocation_log_ref=llm_invocation_log_ref,
        )


class LlmPlanOutput(BaseModel):
    """The lean structured output the plan-stage LLM emits (ADR-0022): an ordered,
    possibly-skipping list of ``action_ids`` plus confidence and rationale. The LLM
    does **not** supply step_ids, inputs, or produced-names — every action in the
    catalog has exactly one valid input recipe, so there is no input decision to
    make; the executable bindings are rebuilt deterministically by the
    orchestrator's re-binding. Descoping ``inputs`` from the model keeps its
    contract honest about what it actually decides (action selection + order)."""

    model_config = ConfigDict(extra="forbid")

    action_ids: list[str]
    confidence: float
    rationale: str


class PlanGeneration(BaseModel):
    """The plan-stage output in full-step form, mapped from ``LlmPlanOutput`` via
    ``plan_generation_from_llm_output`` (step_ids assigned, inputs left empty for
    the orchestrator to re-bind). The service wraps this into a full
    DeliveryPhasePlan with generator/plan_id/version before storing and returning.
    """

    model_config = ConfigDict(extra="forbid")

    applicability: PlanApplicability
    steps: list[PlanStep]
    confidence: float
    rationale: str


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


def plan_generation_from_llm_output(
    llm: LlmPlanOutput, request: PlanRequest
) -> PlanGeneration:
    """Map the lean LLM plan output (ordered action_ids) to a full PlanGeneration.

    step_ids are assigned by position; inputs are left empty (``{}``) and produces
    is left unset — the orchestrator's re-binding rebuilds the executable bindings
    from the deterministic reference plan (ADR-0022). Applicability is taken from
    the request, not the model."""
    return PlanGeneration(
        applicability=PlanApplicability(
            event_type=request.event_type,
            source_system=request.source_system,
            selected_targets=list(request.selected_targets),
        ),
        steps=[
            PlanStep(step_id=i, action_id=action_id)
            for i, action_id in enumerate(llm.action_ids, start=1)
        ],
        confidence=llm.confidence,
        rationale=llm.rationale,
    )
