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


def test_invocation_log_is_append_only_sequential_records(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    key = "mock_lms_skill_mastered.v1_issuer_payload_learncard_issuer"
    record_a = {"status": "succeeded", "call": 1}
    record_b = {"status": "succeeded", "call": 2}

    ref_a = store.store_invocation_log(record_a, key=key)
    ref_b = store.store_invocation_log(record_b, key=key)

    # Each call returns a distinct ref with an incrementing record index.
    assert ref_a == f"llmcall:{key}/0000"
    assert ref_b == f"llmcall:{key}/0001"

    # Both records are independently readable.
    assert store._read(ref_a)["call"] == 1
    assert store._read(ref_b)["call"] == 2


def test_invocation_log_second_call_does_not_overwrite_first(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    key = "mock_lms_skill_mastered.v1_wallet_payload_learncard_wallet"

    ref_first = store.store_invocation_log({"data": "first"}, key=key)
    store.store_invocation_log({"data": "second"}, key=key)

    key_dir = tmp_path / "llmcall" / key
    records = sorted(key_dir.glob("*.json"))
    assert len(records) == 2, "both records must survive; second must not overwrite first"
    # Confirm the first record's content is unchanged after the second write.
    assert store._read(ref_first)["data"] == "first"


def test_reuse_synthetic_ref_without_record_index_raises(tmp_path: Path) -> None:
    # service._reuse() builds a bare ref of the form "llmcall:<key>" with no
    # record index.  Real records live at "llmcall:<key>/NNNN", so _read() on
    # the bare ref tries to open "<base>/llmcall/<key>.json", which does not
    # exist (records live in a subdirectory).  This test pins that current
    # inert behavior so a future invocation-log reader is not surprised.
    store = ArtifactStore(tmp_path)
    key = "mock_lms_skill_mastered.v1_issuer_payload_learncard_issuer"

    # Write a real record so the key directory exists.
    store.store_invocation_log({"status": "succeeded"}, key=key)

    # The bare ref (no "/NNNN" suffix) must NOT resolve.
    with pytest.raises(FileNotFoundError):
        store._read(f"llmcall:{key}")


def test_invocation_log_third_call_gets_index_0002(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    key = "mock_lms_course_completed.v1_issuer_payload_learncard_issuer"

    for i in range(3):
        ref = store.store_invocation_log({"i": i}, key=key)

    assert ref == f"llmcall:{key}/0002"
