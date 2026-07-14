from pathlib import Path

import pytest
from workflow_actions.contracts import (
    DeliveryPhasePlan,
    PlanApplicability,
    PlanGenerator,
)
from workflow_actions.plan_store import FailedPlanError, PlanNotFoundError, PlanStore


def _plan(
    event_type: str = "skill_mastered",
    targets: list[str] | None = None,
) -> DeliveryPhasePlan:
    return DeliveryPhasePlan(
        plan_id=f"{event_type}.v1",
        generator=PlanGenerator(service_version="workflow-actions.v1"),
        applicability=PlanApplicability(
            event_type=event_type,
            source_system="mock_lms",
            selected_targets=targets or ["learncard_issuer", "learncard_wallet"],
        ),
        confidence=0.94,
        rationale="test plan",
    )


def test_store_and_load_plan(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "artifacts")
    plan = _plan()
    ref = store.store_plan(plan)
    assert ref.startswith("plan:")
    loaded = store.load_plan(ref)
    assert loaded.plan_id == plan.plan_id
    assert loaded.applicability.event_type == "skill_mastered"


def test_load_failed_plan_raises(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "artifacts")
    plan = _plan()
    store.store_failed(plan, ["missing step 3"])
    # The failed record occupies the same path — loading raises FailedPlanError.
    appl = plan.applicability
    targets = ".".join(sorted(appl.selected_targets))
    ref = f"plan:{appl.event_type}.{appl.source_system}.{targets}"
    with pytest.raises(FailedPlanError) as exc_info:
        store.load_plan(ref)
    assert "missing step 3" in exc_info.value.validation_errors


def test_load_nonexistent_ref_raises(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "artifacts")
    with pytest.raises(PlanNotFoundError):
        store.load_plan("plan:nonexistent_key")


def test_store_invocation_log(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "artifacts")
    ref = store.store_invocation_log({"stage": "gate", "status": "succeeded"}, key="gate-exec_1")
    assert ref == "llmcall:gate-exec_1"


def test_plan_key_uses_sorted_targets(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "artifacts")
    plan_a = _plan(targets=["learncard_wallet", "learncard_issuer"])
    plan_b = _plan(targets=["learncard_issuer", "learncard_wallet"])
    ref_a = store.store_plan(plan_a)
    ref_b = store.store_plan(plan_b)
    # Same applicability signature → same ref.
    assert ref_a == ref_b
