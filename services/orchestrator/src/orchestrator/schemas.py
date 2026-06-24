"""Orchestrator contracts (aligned to docs/3_design/orchestrator.md).

Typed envelope fields with opaque JSON where the shape varies by step
(FR-OR-22): the full Context Builder bundle and step-specific payloads stay
``dict[str, Any]`` rather than fully-modeled domain objects.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


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

    decision: str  # "continue_to_delivery_targets" | "terminate"
    confidence: float = 1.0
    rationale: str = ""


class InputBinding(BaseModel):
    """How the executor resolves one step input (design §4)."""

    source: str  # "workflow" | "step" | "literal"
    path: str | None = None  # source == "workflow": dotted path into workflow context
    step_id: int | None = None  # source == "step": prior step's full output
    value: Any = None  # source == "literal"


class PlanStep(BaseModel):
    step_id: int
    type: str = "call"  # "call" | "wait" | "for_each" | "terminate" (Phase 1 uses "call")
    action_id: str
    inputs: dict[str, InputBinding] = {}
    produces: str | None = None


class PlanGenerator(BaseModel):
    service_version: str
    model_identifier: str = "stub"
    prompt_template_version: str = ""


class PlanApplicability(BaseModel):
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
    status: str  # "succeeded" | "skipped" | "failed"
    attempt: int = 1
    output: dict[str, Any] = {}
    error: dict[str, Any] | None = None
    started_at: str = ""
    finished_at: str = ""


class ExecutionView(BaseModel):
    """The correlated read model for GET /executions/{id} (FR-OR-19)."""

    execution_id: str
    event_type: str | None = None
    status: str  # created | planning | ready | running | completed | failed
    gate_decision: dict[str, Any] | None = None
    plan_id: str | None = None
    steps: list[StepResult] = []
    result: dict[str, Any] = {}
