"""Tests for the Layer-A validators (design §8 / FR-WA-12/21/22/27)."""

from workflow_actions.contracts import (
    GateGeneration,
    PlanApplicability,
    PlanGeneration,
    PlanStep,
)
from workflow_actions.validators import validate_gate, validate_plan

_REGISTRY: set[tuple[str, str]] = {
    ("resolve_learncard_profile", "call"),
    ("generate_credential_template_mapping", "call"),
    ("generate_credential_template_synthesis", "call"),
    ("execute_credential_template_translation", "call"),
    ("generate_issuer_payload_mapping", "call"),
    ("generate_issuer_payload_synthesis", "call"),
    ("execute_issuer_payload_translation", "call"),
    ("issue_learncard_badge", "call"),
    ("generate_learncard_wallet_payload_mapping", "call"),
    ("execute_learncard_wallet_payload_translation", "call"),
    ("deliver_to_learncard_wallet", "call"),
    ("generate_smartresume_payload_mapping", "call"),
    ("execute_smartresume_payload_translation", "call"),
    ("deliver_to_smartresume", "call"),
}


# ---------------------------------------------------------------------------
# Gate validator
# ---------------------------------------------------------------------------


def test_valid_continue_gate_passes() -> None:
    g = GateGeneration(
        decision="continue", confidence=0.98, rationale="no disqualifier"
    )
    assert validate_gate(g) == []


def test_valid_terminate_gate_passes() -> None:
    g = GateGeneration(
        decision="terminate", confidence=1.0, rationale="sub-competency outcome"
    )
    assert validate_gate(g) == []


def test_unknown_decision_fails() -> None:
    g = GateGeneration(decision="do_something_else", confidence=0.9, rationale="x")
    errors = validate_gate(g)
    assert any("do_something_else" in e for e in errors)


def test_allowed_decisions_set_restricts_values() -> None:
    allowed = {"continue"}
    g = GateGeneration(decision="terminate", confidence=0.9, rationale="x")
    errors = validate_gate(g, allowed_decisions=allowed)
    assert errors


def test_allowed_decisions_set_accepts_valid() -> None:
    allowed = {"continue", "terminate"}
    g = GateGeneration(decision="continue", confidence=0.95, rationale="ok")
    assert validate_gate(g, allowed_decisions=allowed) == []


def test_confidence_out_of_range_fails() -> None:
    g = GateGeneration(decision="continue", confidence=1.5, rationale="x")
    errors = validate_gate(g)
    assert any("confidence" in e for e in errors)


def test_empty_rationale_fails() -> None:
    g = GateGeneration(
        decision="continue", confidence=0.9, rationale="   "
    )
    errors = validate_gate(g)
    assert any("rationale" in e for e in errors)


# ---------------------------------------------------------------------------
# Plan validator — happy path
# ---------------------------------------------------------------------------


def _minimal_valid_plan() -> PlanGeneration:
    """Return a minimal valid plan: one registered step, lean post-#112 shape
    (ordered action_ids; no inputs — the orchestrator re-binds)."""
    return PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(step_id=1, action_id="resolve_learncard_profile", produces="resolved_profile")
        ],
        confidence=0.94,
        rationale="minimal valid plan",
    )


def test_valid_plan_passes() -> None:
    plan = _minimal_valid_plan()
    assert validate_plan(plan, registry=_REGISTRY) == []


def test_plan_confidence_out_of_range_fails() -> None:
    plan = _minimal_valid_plan()
    plan = plan.model_copy(update={"confidence": -0.1})
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("confidence" in e for e in errors)


def test_plan_empty_rationale_fails() -> None:
    plan = _minimal_valid_plan()
    plan = plan.model_copy(update={"rationale": ""})
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("rationale" in e for e in errors)


# ---------------------------------------------------------------------------
# Plan validator — registry conformance
# ---------------------------------------------------------------------------


def test_unknown_action_id_fails_registry_conformance() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="invented_action",
                produces="out",
            )
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("not in action registry" in e for e in errors)


def test_wrong_step_type_fails_registry_conformance() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                type="wait",  # type="wait" not in registry (only "call")
                action_id="resolve_learncard_profile",
                produces="out",
            )
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("not in action registry" in e for e in errors)


# ---------------------------------------------------------------------------
# FR-WA-22: required-step absence does NOT cause Layer-A failure
# ---------------------------------------------------------------------------


def test_plan_without_required_steps_still_passes_layer_a() -> None:
    """A plan that skips expected steps passes Layer-A (required-step presence
    is Layer B / test-harness, FR-WA-22)."""
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer", "learncard_wallet"],
        ),
        steps=[
            # Intentionally missing most Phase-1 steps.
            PlanStep(step_id=1, action_id="resolve_learncard_profile", produces="resolved_profile")
        ],
        confidence=0.5,
        rationale="incomplete but structurally valid",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert errors == []


# ---------------------------------------------------------------------------
# Full Phase-1 plan passes
# ---------------------------------------------------------------------------


def test_full_phase1_plan_passes() -> None:
    """The complete canonical dual-delivery plan (lean post-#112 shape) passes
    all Layer-A gates."""
    action_ids = [
        "resolve_learncard_profile",
        "generate_credential_template_mapping",
        "generate_credential_template_synthesis",
        "execute_credential_template_translation",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "generate_learncard_wallet_payload_mapping",
        "execute_learncard_wallet_payload_translation",
        "deliver_to_learncard_wallet",
        "generate_smartresume_payload_mapping",
        "execute_smartresume_payload_translation",
        "deliver_to_smartresume",
    ]
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer", "learncard_wallet", "smart_resume"],
        ),
        steps=[
            PlanStep(step_id=i, action_id=action_id)
            for i, action_id in enumerate(action_ids, start=1)
        ],
        confidence=0.94,
        rationale="Full dual-target plan.",
    )
    assert validate_plan(plan, registry=_REGISTRY) == []
