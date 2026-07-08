"""Store-level: the step-progress denominator is the plan's step count, not the
number of steps attempted so far (#28 G6 / FR-AU-23)."""

from __future__ import annotations

from orchestrator import planner
from orchestrator.schemas import StepResult
from orchestrator.store import ExecutionStore


def test_list_executions_total_is_plan_step_count_not_attempted() -> None:
    store = ExecutionStore(":memory:")
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer", "learncard_wallet"], "2026-01-01T00:00:00Z"
    )
    assert len(plan.steps) == 8  # guard: the Phase-1 plan is 8 steps

    store.save_plan(plan, "skill_mastered|learncard_issuer,learncard_wallet")
    store.create_execution("exec_fail", "evt", "corr", "skill_mastered")
    store.set_plan("exec_fail", plan.plan_id)
    store.set_status("exec_fail", "failed")
    # Only step 1 was attempted, and it failed: 1 persisted row, but the plan has 8.
    store.save_step(
        "exec_fail",
        StepResult(
            step_id=1, action_id="resolve_learncard_profile", status="failed",
            error={"message": "boom"},
        ),
    )

    (row,) = store.list_executions()
    assert row.step_progress.completed == 0
    assert row.step_progress.total == 8  # from the plan, not the single attempted row


def test_list_executions_total_falls_back_when_no_plan() -> None:
    # A run that terminated at the pre-target gate has no plan_id → 0/0, not an error.
    store = ExecutionStore(":memory:")
    store.create_execution("exec_gate", "evt", "corr", "unsupported")
    store.set_status("exec_gate", "failed")

    (row,) = store.list_executions()
    assert row.step_progress.completed == 0
    assert row.step_progress.total == 0
