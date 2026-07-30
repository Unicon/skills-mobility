from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from field_synthesis.artifact_store import ArtifactStore
from field_synthesis.config import Settings
from field_synthesis.contracts import SynthesisBrief, SynthesisRequest, SynthesisRequestArtifact
from field_synthesis.replay_adapter import ReplayAdapter
from field_synthesis.service import SynthesisService

OPEN_BADGE_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "transformation_type": "open_badge",
    "synthesis_request": {
        "synthesis_request_schema_version": "v1",
        "transformation_type": "open_badge",
        "requests": [
            {
                "placeholder_id": "badge_description",
                "target_path": "badge.description",
                "source_payload_paths": ["source_payloads.learner_context.course.description"],
                "source_payloads": {
                    "learner_context": {"course": {"description": "Core skills course."}}
                },
                "instruction": "Write a concise badge description.",
            },
            {
                "placeholder_id": "badge_criteria",
                "target_path": "badge.criteria",
                "source_payload_paths": [],
                "source_payloads": {"learner_context": {"score": 85}},
                "instruction": "Describe the criteria for earning this badge.",
            },
        ],
    },
}

DEFAULT_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "transformation_type": "unknown_type",
    "synthesis_request": {
        "synthesis_request_schema_version": "v1",
        "transformation_type": "unknown_type",
        "requests": [
            {
                "placeholder_id": "field_a",
                "target_path": "some.field_a",
                "source_payload_paths": [],
                "source_payloads": {},
                "instruction": "Describe field A.",
            }
        ],
    },
}


@pytest.fixture
def open_badge_request() -> SynthesisRequest:
    return SynthesisRequest(**OPEN_BADGE_BODY)


@pytest.fixture
def default_request() -> SynthesisRequest:
    return SynthesisRequest(**DEFAULT_BODY)


@pytest.fixture
def artifact_store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(tmp_path / "artifacts")


@pytest.fixture
def make_service(artifact_store: ArtifactStore) -> Callable[..., SynthesisService]:
    def _make(adapter: Any = None, **kwargs: Any) -> SynthesisService:
        return SynthesisService(
            settings=Settings(mode="replay", artifact_dir=str(artifact_store._base)),
            artifact_store=artifact_store,
            adapter=adapter or ReplayAdapter(),
            **kwargs,
        )

    return _make


def make_brief(
    placeholder_id: str = "field_a",
    target_path: str = "some.field_a",
    instruction: str = "Describe this field.",
    source_payloads: dict[str, Any] | None = None,
) -> SynthesisBrief:
    return SynthesisBrief(
        placeholder_id=placeholder_id,
        target_path=target_path,
        instruction=instruction,
        source_payloads=source_payloads or {},
    )


def make_artifact(
    briefs: list[SynthesisBrief] | None = None,
    transformation_type: str = "test_type",
) -> SynthesisRequestArtifact:
    return SynthesisRequestArtifact(
        transformation_type=transformation_type,
        requests=briefs or [make_brief()],
    )
