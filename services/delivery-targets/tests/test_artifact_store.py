from pathlib import Path
from typing import Any

import pytest
from delivery_targets.artifact_store import (
    ArtifactNotFoundError,
    ArtifactStore,
    FailedArtifactError,
)
from delivery_targets.contracts import SelectionArtifact, TargetSelection


def _artifact(**overrides: Any) -> SelectionArtifact:
    data: dict[str, Any] = {
        "execution_id": "exec_1",
        "event_type": "skill_mastered",
        "source_system": "mock_lms",
        "selections": [
            {
                "delivery_target": "learncard_issuer",
                "confidence": 0.95,
                "rationale": "credential-enabled course",
            }
        ],
    }
    data.update(overrides)
    return SelectionArtifact(**data)


def test_store_and_load_roundtrip_returns_ref(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    art = _artifact()

    ref = store.store_selection(art)

    assert ref.startswith("selection:")
    loaded = store.load_selection(ref)
    assert loaded.execution_id == art.execution_id
    assert len(loaded.selections) == 1
    assert loaded.selections[0].delivery_target == "learncard_issuer"


def test_store_failed_and_load_raises_failed_artifact_error(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)

    ref = store.store_failed("exec_1", "unknown target 'bogus'")

    assert ref == "selection_failed:exec_1"
    # The failed record loads as a failure, never as a successful selection.
    with pytest.raises(FailedArtifactError):
        store.load_selection(ref)


def test_store_failed_does_not_overwrite_previous_success(tmp_path: Path) -> None:
    # Failures live under their own kind: a failed attempt must not destroy a
    # previously-stored success for the same key.
    store = ArtifactStore(tmp_path)
    ok_ref = store.store_selection(_artifact())  # execution_id defaults to exec_1
    store.store_failed("exec_1", "later attempt failed")
    assert store.load_selection(ok_ref).selections


def test_store_invocation_log_returns_ref(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    log: dict[str, Any] = {"execution_id": "exec_1", "status": "succeeded"}

    ref = store.store_invocation_log(log, key="exec_1")

    assert ref == "llmcall:exec_1"
    # The record round-trips — the log content was actually persisted.
    assert store._read(ref) == log


def test_load_missing_ref_raises_artifact_not_found(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactNotFoundError):
        store.load_selection("selection:nonexistent")


def test_selections_roundtrip_preserves_all_targets(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    art = SelectionArtifact(
        execution_id="exec_2",
        event_type="skill_mastered",
        source_system="mock_lms",
        selections=[
            TargetSelection(
                delivery_target="learncard_issuer", confidence=0.95, rationale="r1"
            ),
            TargetSelection(
                delivery_target="learncard_wallet", confidence=0.92, rationale="r2"
            ),
        ],
    )
    ref = store.store_selection(art)
    loaded = store.load_selection(ref)
    assert len(loaded.selections) == 2
    assert loaded.selections[1].delivery_target == "learncard_wallet"
