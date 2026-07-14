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

SKILL_MASTERED_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "learner_context": {
        "learner_id": "learner_42",
        "recipient_profile_id": "smi-demo-learner",
        "credential_enabled": True,
    },
}

COURSE_COMPLETED_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "event_type": "course_completed",
    "source_system": "mock_lms",
    "learner_context": {
        "learner_id": "learner_42",
        "credential_enabled": False,
    },
}


@pytest.fixture
def skill_mastered_request() -> SelectionRequest:
    return SelectionRequest(**SKILL_MASTERED_BODY)


@pytest.fixture
def course_completed_request() -> SelectionRequest:
    return SelectionRequest(**COURSE_COMPLETED_BODY)


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
