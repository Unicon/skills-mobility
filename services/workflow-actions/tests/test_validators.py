"""Tests for the Layer-A validators (design §8 / FR-WA-12/21/22/27)."""

import pytest
from workflow_actions.contracts import (
    GateGeneration,
    InputBinding,
    PlanApplicability,
    PlanGeneration,
    PlanStep,
)
from workflow_actions.validators import WORKFLOW_CONTEXT_KEYS, validate_gate, validate_plan

_REGISTRY: set[tuple[str, str]] = {
    ("resolve_learncard_profile", "call"),
    ("generate_issuer_payload_mapping", "call"),
    ("generate_issuer_payload_synthesis", "call"),
    ("execute_issuer_payload_translation", "call"),
    ("issue_learncard_badge", "call"),
    ("generate_wallet_payload_mapping", "call"),
    ("execute_wallet_payload_translation", "call"),
    ("deliver_to_learncard_wallet", "call"),
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
    """Return a minimal valid plan: one step with a literal binding."""
    return PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={
                    "learner_id_value": InputBinding(source="workflow", path="learner_id_value"),
                    "learner_id_type": InputBinding(source="literal", value="profile_id"),
                },
                produces="resolved_profile",
            )
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
# Plan validator — binding resolvability
# ---------------------------------------------------------------------------


def test_unknown_workflow_path_fails() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={"bad_key": InputBinding(source="workflow", path="nonexistent_key")},
                produces="resolved_profile",
            )
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("workflow path" in e and "nonexistent_key" in e for e in errors)


def test_step_binding_to_later_step_fails() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={"bad_forward_ref": InputBinding(source="step", step_id=2)},
                produces="resolved_profile",
            ),
            PlanStep(
                step_id=2,
                action_id="generate_issuer_payload_mapping",
                produces="issuer_mapping",
            ),
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("does not refer to an earlier step" in e for e in errors)


def test_step_binding_to_non_producing_step_fails() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                produces=None,  # does not produce
            ),
            PlanStep(
                step_id=2,
                action_id="generate_issuer_payload_mapping",
                inputs={"dep": InputBinding(source="step", step_id=1)},
                produces="issuer_mapping",
            ),
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("does not produce" in e for e in errors)


def test_step_binding_missing_step_id_fails() -> None:
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={"missing": InputBinding(source="step")},  # no step_id
                produces="resolved_profile",
            )
        ],
        confidence=0.9,
        rationale="x",
    )
    errors = validate_plan(plan, registry=_REGISTRY)
    assert any("missing step_id" in e for e in errors)


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
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={
                    "learner_id_value": InputBinding(source="workflow", path="learner_id_value")
                },
                produces="resolved_profile",
            )
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
    """The complete 8-step Phase-1 plan should pass all Layer-A gates."""
    steps = [
        PlanStep(
            step_id=1,
            action_id="resolve_learncard_profile",
            inputs={
                "learner_id_type": InputBinding(source="literal", value="profile_id"),
                "learner_id_value": InputBinding(source="workflow", path="learner_id_value"),
                "delivery_config_ref": InputBinding(source="workflow", path="delivery_config_ref"),
            },
            produces="resolved_profile",
        ),
        PlanStep(step_id=2, action_id="generate_issuer_payload_mapping", produces="issuer_mapping"),
        PlanStep(
            step_id=3, action_id="generate_issuer_payload_synthesis", produces="issuer_synthesis"
        ),
        PlanStep(
            step_id=4,
            action_id="execute_issuer_payload_translation",
            inputs={
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "mapping": InputBinding(source="step", step_id=2),
                "synthesis": InputBinding(source="step", step_id=3),
            },
            produces="issuer_payload",
        ),
        PlanStep(
            step_id=5,
            action_id="issue_learncard_badge",
            inputs={"issuer_payload": InputBinding(source="step", step_id=4)},
            produces="issued",
        ),
        PlanStep(step_id=6, action_id="generate_wallet_payload_mapping", produces="wallet_mapping"),
        PlanStep(
            step_id=7,
            action_id="execute_wallet_payload_translation",
            inputs={
                "issued": InputBinding(source="step", step_id=5),
                "resolved_profile": InputBinding(source="step", step_id=1),
                "delivery_target": InputBinding(source="literal", value="learncard_wallet"),
                "mapping": InputBinding(source="step", step_id=6),
            },
            produces="wallet_payload",
        ),
        PlanStep(
            step_id=8,
            action_id="deliver_to_learncard_wallet",
            inputs={"wallet_payload": InputBinding(source="step", step_id=7)},
            produces="delivered",
        ),
    ]
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer", "learncard_wallet"],
        ),
        steps=steps,
        confidence=0.94,
        rationale="Full Phase-1 dual-target plan.",
    )
    assert validate_plan(plan, registry=_REGISTRY) == []


@pytest.mark.parametrize("key", list(WORKFLOW_CONTEXT_KEYS))
def test_all_workflow_context_keys_are_valid_bindings(key: str) -> None:
    """Each known workflow context key must resolve without error."""
    plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={"the_key": InputBinding(source="workflow", path=key)},
                produces="out",
            )
        ],
        confidence=0.9,
        rationale="x",
    )
    assert validate_plan(plan, registry=_REGISTRY) == []
