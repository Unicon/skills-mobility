from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from delivery_targets.artifact_store import ArtifactStore
from delivery_targets.catalog_store import CatalogStore
from delivery_targets.config import Settings
from delivery_targets.contracts import SelectionRequest
from delivery_targets.replay_adapter import ReplayAdapter
from delivery_targets.service import SelectionService

# The routing bifurcation is course subject (design §3/§5): Accounting (ACCY-*)
# pairs the issuer with the LearnCard wallet; Finance (FINC-*) pairs it with
# SmartResume. course_id carries the subject, matching mock-lms's catalog ids.
ACCOUNTING_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "learner_context": {
        "learner_id": "learner_42",
        "course_id": "ACCY-111",
        "recipient_profile_id": "smi-demo-learner",
    },
}

FINANCE_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "event_type": "course_completed",
    "source_system": "mock_lms",
    "learner_context": {
        "learner_id": "learner_42",
        "course_id": "FINC-106",
        "recipient_profile_id": "smi-demo-learner",
    },
}


@pytest.fixture
def accounting_request() -> SelectionRequest:
    return SelectionRequest(**ACCOUNTING_BODY)


@pytest.fixture
def finance_request() -> SelectionRequest:
    return SelectionRequest(**FINANCE_BODY)


@pytest.fixture
def artifact_store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(tmp_path / "artifacts")


@pytest.fixture
def make_service(artifact_store: ArtifactStore) -> Callable[..., SelectionService]:
    def _make(adapter: Any = None, **kwargs: Any) -> SelectionService:
        return SelectionService(
            settings=Settings(mode="replay", artifact_dir=str(artifact_store._base)),
            catalog_store=CatalogStore(),
            artifact_store=artifact_store,
            adapter=adapter or ReplayAdapter(),
            **kwargs,
        )

    return _make
