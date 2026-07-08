"""Orchestrator contracts (aligned to docs/3_design/orchestrator.md).

Typed envelope fields with opaque JSON where the shape varies by step
(FR-OR-22): the full Context Builder bundle and step-specific payloads stay
``dict[str, Any]`` rather than fully-modeled domain objects.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

GateDecisionType = Literal["continue_to_delivery_targets", "terminate"]
InputSource = Literal["workflow", "step", "literal"]
StepType = Literal["call", "wait", "for_each", "terminate"]
StepStatus = Literal["succeeded", "skipped", "failed"]
WorkflowStatus = Literal["created", "planning", "ready", "running", "completed", "failed"]


class WorkflowStartRequest(BaseModel):
    """The workflow-start the Event Consumer hands off (FR-OR-1): the raw event
    envelope plus the ids stamped at ingress."""

    execution_id: str
    event_id: str = ""
    correlation_id: str = ""
    event: dict[str, Any]


class GateDecision(BaseModel):
    """Pre-target Workflow Actions decision artifact — execution-scoped, never
    stored for reuse (ADR-0009, FR-OR-20)."""

    decision: GateDecisionType
    confidence: float = 1.0
    rationale: str = ""


class InputBinding(BaseModel):
    """How the executor resolves one step input (design §4)."""

    source: InputSource
    path: str | None = None  # source == "workflow": dotted path into workflow context
    step_id: int | None = None  # source == "step": prior step's full output
    value: Any = None  # source == "literal"


class PlanStep(BaseModel):
    step_id: int
    type: StepType = "call"  # Phase 1 uses "call"
    action_id: str
    inputs: dict[str, InputBinding] = {}
    produces: str | None = None


class PlanGenerator(BaseModel):
    service_version: str
    model_identifier: str = "stub"
    prompt_template_version: str = ""


class PlanApplicability(BaseModel):
    """The reuse key for a stored delivery-phase plan (ADR-0011): it encodes the
    conditions under which a previously generated plan may be reused for a new
    workflow request — same event type, source system, and selected targets."""

    event_type: str
    source_system: str = "mock_lms"
    selected_targets: list[str] = []


class DeliveryPhasePlan(BaseModel):
    """The second Workflow Actions artifact — the reusable delivery-phase plan
    the executor runs (ADR-0009 stage 2)."""

    plan_schema_version: str = "v1"
    plan_id: str
    generated_at: str = ""
    generator: PlanGenerator
    applicability: PlanApplicability
    confidence: float = 1.0
    rationale: str = ""
    steps: list[PlanStep] = []


class StepResult(BaseModel):
    """One executed step: typed metadata + opaque ``output`` (FR-OR-22)."""

    step_id: int
    action_id: str
    status: StepStatus
    attempt: int = 1
    output: dict[str, Any] = {}
    error: dict[str, Any] | None = None
    started_at: str = ""
    finished_at: str = ""


class ExecutionMetadata(BaseModel):
    """The correlated execution state + audit record for GET /executions/{id}
    (FR-OR-19) — the Orchestrator's execution-log metadata, not a UI view."""

    execution_id: str
    correlation_id: str = ""  # surfaced for the Admin UI cross-app pivot (#28 G3)
    event_type: str | None = None
    status: WorkflowStatus
    gate_decision: dict[str, Any] | None = None
    plan_id: str | None = None
    steps: list[StepResult] = []
    result: dict[str, Any] = {}
    created_at: str = ""  # #28 G4 — list ordering + timestamp column
    updated_at: str = ""
