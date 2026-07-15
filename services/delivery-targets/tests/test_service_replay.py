from typing import Any

import pytest
from delivery_targets.artifact_store import ArtifactStore, FailedArtifactError
from delivery_targets.contracts import (
    LlmCallMeta,
    SelectionGeneration,
    SelectionRequest,
    TargetSelection,
)

_REPLAY_META = LlmCallMeta(provider="replay", model_id="replay", temperature=0.0)


class _CountingAdapter:
    """Wraps an adapter (or returns a fixed generation) and counts select() calls."""

    def __init__(self, inner: Any = None, fixed: SelectionGeneration | None = None) -> None:
        self.inner = inner
        self.fixed = fixed
        self.calls = 0

    def select(
        self, request: SelectionRequest, *, catalog: list[dict[str, Any]]
    ) -> tuple[SelectionGeneration, LlmCallMeta]:
        self.calls += 1
        if self.fixed is not None:
            return self.fixed, _REPLAY_META
        return self.inner.select(request, catalog=catalog)


def test_skill_mastered_replay_end_to_end(
    make_service: Any,
    artifact_store: ArtifactStore,
    skill_mastered_request: SelectionRequest,
) -> None:
    resp = make_service().select(skill_mastered_request)

    assert resp.status == "succeeded"
    assert resp.selection_artifact_ref is not None
    assert resp.llm_invocation_log_ref is not None
    assert "learncard_issuer" in resp.selected_targets
    assert "learncard_wallet" in resp.selected_targets
    # The stored artifact round-trips.
    artifact = artifact_store.load_selection(resp.selection_artifact_ref)
    assert artifact.event_type == "skill_mastered"
    assert len(artifact.selections) == 2


def test_invocation_log_captures_adr0010_metadata(
    make_service: Any,
    artifact_store: ArtifactStore,
    skill_mastered_request: SelectionRequest,
) -> None:
    resp = make_service().select(skill_mastered_request)
    log = artifact_store._read(resp.llm_invocation_log_ref or "")
    # ADR-0010 §60: model-call metadata + the prompt sent + structured output.
    for field in (
        "service", "phase", "event_id", "provider", "model_id", "temperature",
        "input_tokens", "output_tokens", "latency_ms", "system_prompt", "user_prompt",
        "selections",
    ):
        assert field in log, f"missing invocation-log field: {field}"
    assert log["provider"] == "replay"
    assert log["system_prompt"]  # the input a live model would receive
    assert log["selections"][0]["rationale"]  # output rationale (§64)


def test_course_completed_replay_routes_to_smart_resume(
    make_service: Any,
    artifact_store: ArtifactStore,
    course_completed_request: SelectionRequest,
) -> None:
    resp = make_service().select(course_completed_request)

    assert resp.status == "succeeded"
    assert resp.selected_targets == ["smart_resume"]
    artifact = artifact_store.load_selection(resp.selection_artifact_ref or "")
    assert artifact.selections[0].delivery_target == "smart_resume"


def test_invalid_generation_yields_failed_status_and_stored_failed_artifact(
    make_service: Any,
    artifact_store: ArtifactStore,
    skill_mastered_request: SelectionRequest,
) -> None:
    # An empty selection is a validation failure.
    bad = SelectionGeneration(selections=[])
    resp = make_service(adapter=_CountingAdapter(fixed=bad)).select(skill_mastered_request)

    assert resp.status == "failed"
    assert resp.selection_artifact_ref is None
    assert resp.llm_invocation_log_ref is not None
    # The failed record is stored but cannot be loaded as a success.
    with pytest.raises(FailedArtifactError):
        artifact_store.load_selection("selection:exec_1")


def test_exactly_one_adapter_attempt_no_hidden_repair(
    make_service: Any,
    skill_mastered_request: SelectionRequest,
) -> None:
    # Even when the generation fails validation, there is no second attempt (FR-DT-14).
    bad = SelectionGeneration(selections=[])
    adapter = _CountingAdapter(fixed=bad)
    make_service(adapter=adapter).select(skill_mastered_request)
    assert adapter.calls == 1


def test_unknown_event_type_falls_back_to_default_fixture(
    make_service: Any,
    artifact_store: ArtifactStore,
) -> None:
    unknown_event = SelectionRequest(
        execution_id="exec_99",
        event_id="evt_99",
        event_type="unknown_event_type",
        source_system="mock_lms",
        learner_context={},
    )
    resp = make_service().select(unknown_event)
    # Default fixture selects learncard_issuer + learncard_wallet (FR-DT-35).
    assert resp.status == "succeeded"
    assert "learncard_issuer" in resp.selected_targets
    assert "learncard_wallet" in resp.selected_targets


def test_unknown_target_in_generation_stores_failed_artifact(
    make_service: Any,
    artifact_store: ArtifactStore,
    skill_mastered_request: SelectionRequest,
) -> None:
    bad = SelectionGeneration(
        selections=[
            TargetSelection(
                delivery_target="invented_system", confidence=0.9, rationale="invented"
            )
        ]
    )
    resp = make_service(adapter=_CountingAdapter(fixed=bad)).select(skill_mastered_request)
    assert resp.status == "failed"
