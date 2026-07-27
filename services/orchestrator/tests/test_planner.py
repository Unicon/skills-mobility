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

    assert plan.plan_id == "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
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


def test_delivery_phase_plan_finance_pairing_issuer_plus_smartresume():
    # The canonical Finance selection: issuance always runs (LearnCard is the
    # only issuer), SmartResume is the final delivery step — no wallet steps.
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer", "smart_resume"], "2026-06-24T00:00:00Z"
    )

    assert plan.plan_id == "phase1-skill_mastered.learncard_issuer.smart_resume.v1"
    assert [s.action_id for s in plan.steps] == [
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "deliver_to_smartresume",
    ]
    # SmartResume step is step_id 6 when no wallet branch
    sr_step = plan.steps[-1]
    assert sr_step.step_id == 6
    assert sr_step.produces == "delivered_smartresume"


def test_delivery_phase_plan_smart_resume_only_still_issues():
    # Even without learncard_issuer in the selection, issuance runs — it is the
    # only issuer, so the plan cannot deliver an unissued credential.
    plan = planner.delivery_phase_plan("skill_mastered", ["smart_resume"], "2026-06-24T00:00:00Z")

    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert action_ids[-1] == "deliver_to_smartresume"
    assert "deliver_to_learncard_wallet" not in action_ids


def test_delivery_phase_plan_wallet_targets():
    for targets in (["learncard_issuer", "learncard_wallet"], ["learncard_wallet"]):
        plan = planner.delivery_phase_plan("skill_mastered", targets, "2026-06-24T00:00:00Z")
        action_ids = [s.action_id for s in plan.steps]
        assert "issue_learncard_badge" in action_ids
        assert "deliver_to_learncard_wallet" in action_ids
        assert "deliver_to_smartresume" not in action_ids


def test_delivery_phase_plan_issuer_only_falls_back_to_wallet_default():
    # learncard_issuer alone names no final delivery step, so the Phase-1
    # backward-compatible default applies: deliver to the wallet.
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer"], "2026-06-24T00:00:00Z"
    )
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert "deliver_to_smartresume" not in action_ids


def test_delivery_phase_plan_all_targets():
    all_targets = ["learncard_issuer", "learncard_wallet", "smart_resume"]
    plan = planner.delivery_phase_plan("skill_mastered", all_targets, "2026-06-24T00:00:00Z")

    assert plan.plan_id == (
        "phase1-skill_mastered.learncard_issuer.learncard_wallet.smart_resume.v1"
    )
    action_ids = [s.action_id for s in plan.steps]
    assert action_ids == [
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "generate_wallet_payload_mapping",
        "execute_wallet_payload_translation",
        "deliver_to_learncard_wallet",
        "deliver_to_smartresume",
    ]
    # SmartResume is step_id 9 when LearnCard branch is present
    sr_step = plan.steps[-1]
    assert sr_step.step_id == 9


def test_delivery_phase_plan_empty_targets_emits_learncard_default():
    plan = planner.delivery_phase_plan("skill_mastered", [], "2026-06-24T00:00:00Z")

    assert plan.plan_id == "phase1-skill_mastered.v1"
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert "deliver_to_smartresume" not in action_ids


def test_delivery_phase_plan_step_bindings_valid():
    """Verify each step's step_id references exist for source=step bindings."""
    all_targets = ["learncard_issuer", "learncard_wallet", "smart_resume"]
    for targets in (["learncard_issuer", "learncard_wallet"], ["smart_resume"], all_targets):
        plan = planner.delivery_phase_plan("skill_mastered", targets, "2026-06-24T00:00:00Z")
        step_ids = {s.step_id for s in plan.steps}
        for step in plan.steps:
            for binding in step.inputs.values():
                if binding.source == "step":
                    assert binding.step_id in step_ids, (
                        f"step {step.step_id} ({step.action_id}) references missing "
                        f"step_id={binding.step_id}"
                    )


def test_plan_id_is_target_aware():
    plan_lc = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer", "learncard_wallet"], "2026-06-24T00:00:00Z"
    )
    plan_sr = planner.delivery_phase_plan(
        "skill_mastered", ["smart_resume"], "2026-06-24T00:00:00Z"
    )
    plan_all = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer", "learncard_wallet", "smart_resume"],
        "2026-06-24T00:00:00Z",
    )
    assert plan_lc.plan_id != plan_sr.plan_id
    assert plan_lc.plan_id != plan_all.plan_id
    assert plan_sr.plan_id != plan_all.plan_id


def test_applicability_key_includes_event_and_targets():
    key = planner.applicability_key("skill_mastered", ["learncard_wallet", "learncard_issuer"])
    assert key == "skill_mastered|learncard_issuer,learncard_wallet"
