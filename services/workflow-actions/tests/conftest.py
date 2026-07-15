from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from workflow_actions.config import Settings
from workflow_actions.contracts import GateRequest, PlanRequest
from workflow_actions.plan_store import PlanStore
from workflow_actions.replay_adapter import ReplayAdapter
from workflow_actions.service import WorkflowActionsService

SKILL_MASTERED_GATE_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "event_type": "skill_mastered",
    "event": {
        "metadata": {"event_name": "learning_outcome_result_created"},
        "learner_id": "learner_42",
    },
    "context_bundle": {
        "learner_id_value": "smi-demo-learner",
        "delivery_config_ref": "config_lc",
        "bundle": "bundle_data",
        "issuer_id": "did:example:issuer",
    },
    "policy_context": None,
}

SKILL_MASTERED_PLAN_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "event": {
        "metadata": {"event_name": "learning_outcome_result_created"},
        "learner_id": "learner_42",
    },
    "context_bundle": {
        "learner_id_value": "smi-demo-learner",
        "delivery_config_ref": "config_lc",
        "bundle": "bundle_data",
        "issuer_id": "did:example:issuer",
    },
    "selected_targets": ["learncard_issuer", "learncard_wallet"],
}


@pytest.fixture
def skill_mastered_gate_request() -> GateRequest:
    return GateRequest(**SKILL_MASTERED_GATE_BODY)


@pytest.fixture
def skill_mastered_plan_request() -> PlanRequest:
    return PlanRequest(**SKILL_MASTERED_PLAN_BODY)


@pytest.fixture
def plan_store(tmp_path: Path) -> PlanStore:
    return PlanStore(tmp_path / "artifacts")


@pytest.fixture
def make_service(plan_store: PlanStore) -> Callable[..., WorkflowActionsService]:
    def _make(adapter: Any = None, **kwargs: Any) -> WorkflowActionsService:
        return WorkflowActionsService(
            settings=Settings(mode="replay", artifact_dir=str(plan_store._base)),
            plan_store=plan_store,
            adapter=adapter or ReplayAdapter(),
            **kwargs,
        )

    return _make
