"""Planner artifacts: event-type mapping, the two-stage gate, and the
deterministic delivery-phase plan shape (ADR-0009 / FR-OR-5,10,11,12)."""

from __future__ import annotations

from orchestrator import planner


def test_event_type_mapping():
    skill = {"metadata": {"event_name": "learning_outcome_result_created"}}
    course = {"metadata": {"event_name": "course_completed"}}
    assert planner.event_type_of(skill) == "skill_mastered"
    assert planner.event_type_of(course) == "course_completed"


def test_gate_continues_for_supported_events():
    for et in ("skill_mastered", "course_completed"):
        assert planner.pre_target_gate(et).decision == "continue"


def test_gate_terminates_for_unsupported_event():
    gate = planner.pre_target_gate("badge_awarded")
    assert gate.decision == "terminate"


def test_delivery_phase_plan_shape():
    targets = planner.select_delivery_targets()
    plan = planner.delivery_phase_plan("skill_mastered", targets, "2026-06-24T00:00:00Z")

    assert plan.plan_id == "phase1-skill_mastered.v1"
    assert plan.applicability.selected_targets == ["learncard_issuer", "learncard_wallet"]
    assert all(step.type == "call" for step in plan.steps)
    assert [s.action_id for s in plan.steps] == [
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "generate_wallet_payload_mapping",
        "execute_wallet_payload_translation",
        "deliver_to_learncard_wallet",
    ]


def test_applicability_key_includes_event_and_targets():
    key = planner.applicability_key("skill_mastered", ["learncard_wallet", "learncard_issuer"])
    assert key == "skill_mastered|learncard_issuer,learncard_wallet"
