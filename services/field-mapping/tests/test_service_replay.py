from typing import Any

import pytest
from field_mapping.artifact_store import ArtifactStore, FailedArtifactError, stable_key
from field_mapping.contracts import LlmCallMeta, MappingGeneration, MappingRequest
from field_mapping.replay_adapter import ReplayAdapter

_REPLAY_META = LlmCallMeta(provider="replay", model_id="replay", temperature=0.0)


class _CountingAdapter:
    """Wraps an adapter (or returns a fixed generation) and counts generate() calls."""

    def __init__(self, inner: Any = None, fixed: MappingGeneration | None = None) -> None:
        self.inner = inner
        self.fixed = fixed
        self.calls = 0

    def generate(
        self, request: MappingRequest, *, target_schema: dict[str, Any]
    ) -> tuple[MappingGeneration, LlmCallMeta]:
        self.calls += 1
        if self.fixed is not None:
            return self.fixed, _REPLAY_META
        return self.inner.generate(request, target_schema=target_schema)


def test_invocation_log_captures_adr0010_metadata(
    make_service: Any, artifact_store: ArtifactStore, wallet_request: MappingRequest
) -> None:
    resp = make_service().map(wallet_request)
    log = artifact_store._read(resp.llm_invocation_log_ref or "")
    # ADR-0010 §60: model-call metadata + the prompt sent + structured output.
    for field in (
        "service", "phase", "event_id", "provider", "model_id", "temperature",
        "input_tokens", "output_tokens", "latency_ms", "system_prompt", "user_prompt",
        "jsonata", "confidence", "rationale",
    ):
        assert field in log, f"missing invocation-log field: {field}"
    assert log["provider"] == "replay"
    assert log["system_prompt"]  # the input a live model would receive


def test_wallet_payload_replay_end_to_end(
    make_service: Any, artifact_store: ArtifactStore, wallet_request: MappingRequest
) -> None:
    resp = make_service().map(wallet_request)

    assert resp.status == "succeeded"
    assert resp.requires_synthesis is False
    assert resp.synthesis_request_ref is None
    assert resp.llm_invocation_log_ref is not None
    # the mapping ref resolves to a stored, synthesis-free artifact
    artifact = artifact_store.load_mapping(resp.mapping_artifact_ref or "")
    assert artifact.transformation_type.value == "wallet_payload"
    assert artifact.placeholder_ids == []


def test_issuer_payload_replay_produces_placeholders_and_synthesis_request(
    make_service: Any, artifact_store: ArtifactStore, issuer_request: MappingRequest
) -> None:
    resp = make_service().map(issuer_request)

    assert resp.status == "succeeded"
    assert resp.requires_synthesis is True
    assert resp.synthesis_request_ref is not None
    synth = artifact_store.load_synthesis_request(resp.synthesis_request_ref)
    assert synth.requests[0].placeholder_id == "achievement_description"
    artifact = artifact_store.load_mapping(resp.mapping_artifact_ref or "")
    assert artifact.placeholder_ids == ["achievement_description"]


def test_invalid_fixture_yields_failed_status_and_stored_failed_artifact(
    make_service: Any, artifact_store: ArtifactStore, wallet_request: MappingRequest
) -> None:
    # A generation with unparseable JSONata and a missing required target field.
    bad = MappingGeneration(jsonata='{ "recipient_profile_id": ', confidence=0.5, rationale="x")
    resp = make_service(adapter=_CountingAdapter(fixed=bad)).map(wallet_request)

    assert resp.status == "failed"
    assert resp.mapping_artifact_ref is None
    assert resp.llm_invocation_log_ref is not None
    key = stable_key(
        source_system=wallet_request.source_system,
        fetch_profile_id=wallet_request.fetch_profile_id,
        transformation_type=wallet_request.transformation_type,
        delivery_target=wallet_request.delivery_target,
    )
    with pytest.raises(FailedArtifactError):
        artifact_store.load_mapping(f"mapping:{key}")


def test_exactly_one_adapter_attempt_no_hidden_repair(
    make_service: Any, wallet_request: MappingRequest
) -> None:
    # Even when the generation fails validation, there is no second attempt (FR-FM-18).
    bad = MappingGeneration(jsonata="{ ", confidence=0.1, rationale="x")
    adapter = _CountingAdapter(fixed=bad)
    make_service(adapter=adapter).map(wallet_request)
    assert adapter.calls == 1


def test_reuse_disabled_by_default_generates_fresh(
    make_service: Any, wallet_request: MappingRequest
) -> None:
    adapter = _CountingAdapter(inner=ReplayAdapter())
    service = make_service(adapter=adapter)  # reuse_stored defaults to False
    service.map(wallet_request)
    service.map(wallet_request)
    assert adapter.calls == 2


def test_course_completed_wallet_replay_end_to_end(
    make_service: Any,
    artifact_store: ArtifactStore,
    course_wallet_request: MappingRequest,
) -> None:
    resp = make_service().map(course_wallet_request)

    assert resp.status == "succeeded"
    assert resp.requires_synthesis is False
    assert resp.synthesis_request_ref is None
    artifact = artifact_store.load_mapping(resp.mapping_artifact_ref or "")
    assert artifact.transformation_type.value == "wallet_payload"
    assert artifact.placeholder_ids == []


def test_course_completed_issuer_replay_produces_synthesis_request(
    make_service: Any,
    artifact_store: ArtifactStore,
    course_issuer_request: MappingRequest,
) -> None:
    resp = make_service().map(course_issuer_request)

    assert resp.status == "succeeded"
    assert resp.requires_synthesis is True
    assert resp.synthesis_request_ref is not None
    synth = artifact_store.load_synthesis_request(resp.synthesis_request_ref)
    assert synth.requests[0].placeholder_id == "course_achievement_description"
    artifact = artifact_store.load_mapping(resp.mapping_artifact_ref or "")
    assert artifact.placeholder_ids == ["course_achievement_description"]
