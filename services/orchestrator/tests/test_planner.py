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
        "generate_credential_template_mapping",
        "generate_credential_template_synthesis",
        "execute_credential_template_translation",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "generate_smartresume_payload_mapping",
        "execute_smartresume_payload_translation",
        "deliver_to_smartresume",
    ]
    # SmartResume delivery lands at step_id 11 when there is no wallet branch
    # (steps 9-11 are the SmartResume mapping/translation/delivery).
    sr_step = plan.steps[-1]
    assert sr_step.step_id == 11
    assert sr_step.produces == "delivered_smartresume"


def test_delivery_phase_plan_smart_resume_only_still_issues():
    # Even without learncard_issuer in the selection, issuance runs — it is the
    # only issuer, so the plan cannot deliver an unissued credential.
    plan = planner.delivery_phase_plan("skill_mastered", ["smart_resume"], "2026-06-24T00:00:00Z")

    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert action_ids[-1] == "deliver_to_smartresume"
    assert "deliver_to_learncard_wallet" not in action_ids


def test_delivery_phase_plan_wallet_only_target():
    # issuer+wallet is covered by test_delivery_phase_plan_shape; this covers the
    # bare-wallet selection.
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_wallet"], "2026-06-24T00:00:00Z"
    )
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert "deliver_to_smartresume" not in action_ids


def test_delivery_phase_plan_wallet_plus_smartresume_without_explicit_issuer():
    # Both final targets selected but learncard_issuer not explicitly named:
    # both delivery branches emit, and issuance still runs (hard invariant).
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_wallet", "smart_resume"], "2026-06-24T00:00:00Z"
    )
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert action_ids[-1] == "deliver_to_smartresume"
    assert len(plan.steps) == 14
    assert plan.steps[-1].step_id == 14


def test_selection_without_issuer_logs_error_but_still_issues(caplog):
    # Issuance is a hard invariant (the delivery branches consume the issued
    # credential), so a non-empty selection omitting learncard_issuer still
    # issues — but the selection/plan mismatch is recorded at failure level.
    import logging

    with caplog.at_level(logging.ERROR, logger="orchestrator.planner"):
        plan = planner.delivery_phase_plan(
            "skill_mastered", ["smart_resume"], "2026-06-24T00:00:00Z"
        )
    assert "issue_learncard_badge" in [s.action_id for s in plan.steps]
    assert any(
        "learncard_issuer not being selected" in r.message for r in caplog.records
    )


def test_routine_selections_do_not_log_the_mismatch_error(caplog):
    import logging

    with caplog.at_level(logging.ERROR, logger="orchestrator.planner"):
        planner.delivery_phase_plan(
            "skill_mastered", ["learncard_issuer", "learncard_wallet"], "2026-06-24T00:00:00Z"
        )
        planner.delivery_phase_plan("skill_mastered", [], "2026-06-24T00:00:00Z")
    assert caplog.records == []


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
    # SmartResume delivery is step_id 14 when the wallet branch is present.
    sr_step = plan.steps[-1]
    assert sr_step.step_id == 14


def test_delivery_phase_plan_empty_targets_emits_learncard_default():
    plan = planner.delivery_phase_plan("skill_mastered", [], "2026-06-24T00:00:00Z")

    assert plan.plan_id == "phase1-skill_mastered.v1"
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert "deliver_to_smartresume" not in action_ids


def test_unrecognized_target_falls_back_to_wallet_default(caplog):
    # A typo / not-yet-handled target name must not silently change the plan
    # shape: no known final target -> the Phase-1 wallet default, and the
    # issuer-mismatch error records that the selection didn't name the issuer.
    import logging

    with caplog.at_level(logging.ERROR, logger="orchestrator.planner"):
        plan = planner.delivery_phase_plan(
            "skill_mastered", ["frobnicate_wallet"], "2026-06-24T00:00:00Z"
        )
    action_ids = [s.action_id for s in plan.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" in action_ids
    assert "deliver_to_smartresume" not in action_ids
    assert any("learncard_issuer not being selected" in r.message for r in caplog.records)


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


def test_every_planned_action_id_has_a_registered_implementation():
    # #124 guarded: a plan action_id with no ACTIONS entry silently never connects
    # to its wiring (the #89 wallet rename briefly created exactly that gap).
    from orchestrator.actions import ACTIONS

    for targets in (
        ["learncard_issuer", "learncard_wallet"],
        ["learncard_issuer", "smart_resume"],
        ["learncard_issuer", "learncard_wallet", "smart_resume"],
    ):
        plan = planner.delivery_phase_plan("skill_mastered", targets, "2026-06-24T00:00:00Z")
        missing = [s.action_id for s in plan.steps if s.action_id not in ACTIONS]
        assert missing == [], f"unregistered action ids for {targets}: {missing}"
