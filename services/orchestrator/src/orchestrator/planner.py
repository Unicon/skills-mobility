"""Planner path artifacts (ADR-0009 two-stage hierarchical model).

Phase 1 satisfies the Workflow Actions / Delivery Targets seams with deterministic
stubs, but returns the *intended* target-PoC artifact shapes (FR-OR-5): a
pre-target gate decision and a delivery-phase plan. Swapping in the real LLM
Decision Services later is a planner change, not an executor change.
"""

from __future__ import annotations

from typing import Any

from orchestrator.schemas import (
    DeliveryPhasePlan,
    GateDecision,
    InputBinding,
    PlanApplicability,
    PlanGenerator,
    PlanStep,
)

# Canvas Live Event names → the logical event types Phase 1 supports (FR-OR-9).
_EVENT_TYPE_BY_NAME = {
    "learning_outcome_result_created": "skill_mastered",
    "course_completed": "course_completed",
}
_SUPPORTED = frozenset(_EVENT_TYPE_BY_NAME.values())
_PHASE1_TARGETS = ["learncard_issuer", "learncard_wallet"]
# The deterministic Context Builder fetch profile per event type — supplied to the
# Field Mapping seam so it resolves its source catalogs (#27 §4/§5).
_FETCH_PROFILE_BY_EVENT = {
    "skill_mastered": "skill_mastered.v1",
    "course_completed": "course_completed.v1",
}


def event_type_of(event: dict[str, Any]) -> str:
    name = str(event.get("metadata", {}).get("event_name", ""))
    return _EVENT_TYPE_BY_NAME.get(name, name)


def pre_target_gate(event_type: str) -> GateDecision:
    """Stage-1 Workflow Actions stub: continue for the supported happy paths,
    terminate otherwise (FR-OR-10)."""
    if event_type in _SUPPORTED:
        return GateDecision(
            decision="continue_to_delivery_targets",
            rationale="Deterministic Phase 1 happy-path gate decision.",
        )
    return GateDecision(
        decision="terminate",
        rationale=f"Unsupported event type for Phase 1: {event_type or '(unknown)'}.",
    )


def select_delivery_targets() -> list[str]:
    """Delivery Targets stub: always LearnCard issuance + wallet (FR-OR-11)."""
    return list(_PHASE1_TARGETS)


def applicability_key(event_type: str, targets: list[str]) -> str:
    """Reusable-plan lookup key — event type + selected targets (ADR-0011)."""
    return f"{event_type}|{','.join(sorted(targets))}"


def _step(step_id: int, action_id: str, inputs: dict[str, InputBinding], produces: str) -> PlanStep:
    return PlanStep(step_id=step_id, action_id=action_id, inputs=inputs, produces=produces)


def _phase1_steps(fetch_profile_id: str) -> list[PlanStep]:
    """The fixed Phase-1 delivery-phase sequence (design §5). Field Mapping /
    Field Synthesis seams are preserved as explicit steps (FR-OR-14/15); the
    mapping steps carry the source_system + fetch_profile_id + upstream data the
    Field Mapping service needs to build its request (#27 §4)."""
    return [
        _step(
            1,
            "resolve_learncard_profile",
            {
                "learner_id_type": InputBinding(source="literal", value="email"),
                "learner_id_value": InputBinding(source="workflow", path="learner_id_value"),
                "delivery_config_ref": InputBinding(source="workflow", path="delivery_config_ref"),
            },
            "resolved_profile",
        ),
        _step(
            2,
            "generate_issuer_payload_mapping",
            {
                # transformation_type and delivery_target are independent plan
                # literals, not a derived pair (#27 §4); synthesis_allowed is the
                # plan's permission gate for Field Synthesis this phase (#27 §6).
                "transformation_type": InputBinding(source="literal", value="issuer_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "synthesis_allowed": InputBinding(source="literal", value=True),
                # Source resolution + payload inputs for the Field Mapping request.
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
            },
            "issuer_mapping",
        ),
        _step(
            3,
            "generate_issuer_payload_synthesis",
            {
                "transformation_type": InputBinding(source="literal", value="issuer_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "mapping": InputBinding(source="step", step_id=2),
            },
            "issuer_synthesis",
        ),
        _step(
            4,
            "execute_issuer_payload_translation",
            {
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
                # Seam bindings for the real transformation services (Phase-1 stubs
                # ignore them, but the executor wiring must be in place — FR-OR-14).
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "mapping": InputBinding(source="step", step_id=2),
                "synthesis": InputBinding(source="step", step_id=3),
            },
            "issuer_payload",
        ),
        _step(
            5,
            "issue_learncard_badge",
            {"issuer_payload": InputBinding(source="step", step_id=4)},
            "issued",
        ),
        _step(
            6,
            "generate_wallet_payload_mapping",
            {
                # The wallet phase provisions no Field Synthesis step, so the plan
                # passes synthesis_allowed=false — a property of this plan, not a
                # rule hardcoded in the FM service or the executor (#27 §6).
                "transformation_type": InputBinding(source="literal", value="wallet_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_wallet"),
                "synthesis_allowed": InputBinding(source="literal", value=False),
                # Source resolution + the issued badge for the Field Mapping request.
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "issued": InputBinding(source="step", step_id=5),
                "resolved_profile": InputBinding(source="step", step_id=1),
            },
            "wallet_mapping",
        ),
        _step(
            7,
            "execute_wallet_payload_translation",
            {
                "issued": InputBinding(source="step", step_id=5),
                "resolved_profile": InputBinding(source="step", step_id=1),
                # Seam bindings for the real transformation services (FR-OR-15) —
                # wallet pass has no synthesis (per the #25 FR-OR-15 table).
                "delivery_target": InputBinding(source="literal", value="learncard_wallet"),
                "mapping": InputBinding(source="step", step_id=6),
            },
            "wallet_payload",
        ),
        _step(
            8,
            "deliver_to_learncard_wallet",
            {"wallet_payload": InputBinding(source="step", step_id=7)},
            "delivered",
        ),
    ]


def delivery_phase_plan(
    event_type: str, targets: list[str], generated_at: str
) -> DeliveryPhasePlan:
    """Stage-2 Workflow Actions stub: the delivery-phase plan for the selected
    targets (FR-OR-12). Same step structure for both supported event types."""
    return DeliveryPhasePlan(
        plan_id=f"phase1-{event_type}.v1",
        generated_at=generated_at,
        generator=PlanGenerator(
            service_version="phase1-workflow-actions-stub.v1",
            prompt_template_version="phase1-static-plan.v1",
        ),
        applicability=PlanApplicability(event_type=event_type, selected_targets=list(targets)),
        rationale="Deterministic Phase 1 LearnCard workflow.",
        steps=_phase1_steps(_FETCH_PROFILE_BY_EVENT.get(event_type, f"{event_type}.v1")),
    )
