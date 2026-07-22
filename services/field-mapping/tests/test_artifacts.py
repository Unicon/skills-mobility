import pytest
from field_mapping.contracts import (
    MappingArtifact,
    SynthesisRequestEntry,
    placeholder_id_from_path,
)
from pydantic import ValidationError


def test_mapping_artifact_requires_schema_version() -> None:
    art = MappingArtifact(
        transformation_type="issuer_payload",
        source_system="mock_lms",
        fetch_profile_id="skill_mastered.v1",
        delivery_target="learncard_issuer",
        target_schema_ref="schema:issuer_payload:v1",
        jsonata="{}",
    )
    assert art.model_dump()["mapping_artifact_schema_version"] == "v1"
    assert art.placeholder_ids == []  # defaults to no synthesis-backed fields


def test_synthesis_request_requires_paths_or_snapshot() -> None:
    common = {"placeholder_id": "achievement_description", "target_path": "achievement.description"}

    with pytest.raises(ValidationError):  # neither representation
        SynthesisRequestEntry(**common, instruction="x")

    SynthesisRequestEntry(  # path references only
        **common, source_payload_paths=["source_payloads.learner_context.desc"], instruction="x"
    )
    SynthesisRequestEntry(  # concrete snapshot only
        **common, source_payloads={"learner_context": {"desc": "..."}}, instruction="x"
    )


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("achievement.description", "achievement_description"),
        ("credentialSubject.achievement.description", "achievement_description"),
        ("achievement.humanCode", "achievement_human_code"),
    ],
)
def test_placeholder_id_snake_case_derivation(path: str, expected: str) -> None:
    assert placeholder_id_from_path(path) == expected
