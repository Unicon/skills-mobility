from pathlib import Path
from typing import Any

import pytest
from field_mapping.artifact_store import ArtifactStore, FailedArtifactError
from field_mapping.contracts import MappingArtifact


def _mapping(**overrides: Any) -> MappingArtifact:
    data: dict[str, Any] = {
        "transformation_type": "issuer_payload",
        "source_system": "mock_lms",
        "fetch_profile_id": "skill_mastered.v1",
        "delivery_target": "learncard_issuer",
        "target_schema_ref": "schema:issuer_payload:v1",
        "jsonata": "{ 'name': source_payloads.learner_context.name }",
        "placeholder_ids": ["achievement_description"],
    }
    data.update(overrides)
    return MappingArtifact(**data)


def test_store_and_load_roundtrip_returns_ref(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    art = _mapping()

    ref = store.store_mapping(art)

    assert ref.startswith("mapping:")
    assert store.load_mapping(ref) == art


def test_failed_artifact_stored_with_validation_errors_and_not_loadable_as_success(
    tmp_path: Path,
) -> None:
    store = ArtifactStore(tmp_path)
    errors = ["jsonata parse error: unexpected token"]

    ref = store.store_failed_mapping(
        source_system="mock_lms",
        fetch_profile_id="skill_mastered.v1",
        transformation_type="issuer_payload",  # type: ignore[arg-type]
        delivery_target="learncard_issuer",  # type: ignore[arg-type]
        validation_errors=errors,
    )

    # It is persisted (audit trail), but cannot be loaded as a successful mapping.
    assert (tmp_path / "mapping").exists()
    with pytest.raises(FailedArtifactError) as exc:
        store.load_mapping(ref)
    assert exc.value.validation_errors == errors
