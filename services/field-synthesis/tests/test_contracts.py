import pytest
from field_synthesis.contracts import (
    LlmCallMeta,
    SynthesisBrief,
    SynthesisGeneration,
    SynthesisRequest,
    SynthesisRequestArtifact,
    SynthesisResponse,
    SynthesisResultArtifact,
)
from pydantic import ValidationError

_SEAM_KEYS = {"status", "synthesis_result_ref", "llm_invocation_log_ref", "values"}


# --- SynthesisBrief ---


def test_synthesis_brief_defaults() -> None:
    brief = SynthesisBrief(
        placeholder_id="field_a",
        target_path="some.field_a",
        instruction="Write a description.",
    )
    assert brief.source_payload_paths == []
    assert brief.source_payloads == {}


def test_synthesis_brief_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SynthesisBrief(  # type: ignore[call-arg]
            placeholder_id="x",
            target_path="y",
            instruction="z",
            unknown_field="bad",
        )


# --- SynthesisRequestArtifact ---


def test_synthesis_request_artifact_defaults() -> None:
    artifact = SynthesisRequestArtifact(
        transformation_type="issuer_payload",
        requests=[],
    )
    assert artifact.synthesis_request_schema_version == "v1"


def test_synthesis_request_artifact_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        SynthesisRequestArtifact(  # type: ignore[call-arg]
            transformation_type="issuer_payload",
            requests=[],
            extra="nope",
        )


# --- SynthesisRequest ---


def test_synthesis_request_optional_fields_default_to_none() -> None:
    req = SynthesisRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="credential_template",
    )
    assert req.synthesis_request_ref is None
    assert req.synthesis_request is None


def test_synthesis_request_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        SynthesisRequest(  # type: ignore[call-arg]
            execution_id="exec_1",
            event_id="evt_1",
            transformation_type="credential_template",
            bogus="bad",
        )


# --- SynthesisResponse ---


def test_response_envelope_has_exact_seam_keys() -> None:
    resp = SynthesisResponse.succeeded(
        synthesis_result_ref="synthesis_result:exec_1",
        llm_invocation_log_ref="llmcall:exec_1",
        values={"achievement_description": "You did it."},
    )
    assert set(resp.model_dump().keys()) == _SEAM_KEYS
    assert resp.status == "succeeded"
    assert resp.synthesis_result_ref == "synthesis_result:exec_1"


def test_failed_response_has_none_result_ref() -> None:
    resp = SynthesisResponse.failed(llm_invocation_log_ref="llmcall:exec_1")
    assert resp.status == "failed"
    assert resp.synthesis_result_ref is None


def test_failed_response_accepts_no_log_ref() -> None:
    resp = SynthesisResponse.failed()
    assert resp.llm_invocation_log_ref is None


def test_response_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        SynthesisResponse(  # type: ignore[call-arg]
            status="succeeded",
            synthesis_result_ref="x",
            llm_invocation_log_ref="y",
            unexpected="bad",
        )


# --- SynthesisGeneration ---


def test_synthesis_generation_optional_confidence_rationale() -> None:
    gen = SynthesisGeneration(values={"field_a": "text"})
    assert gen.confidence is None
    assert gen.rationale is None


def test_synthesis_generation_round_trip() -> None:
    gen = SynthesisGeneration(
        values={"field_a": "text", "field_b": "more text"},
        confidence=0.9,
        rationale="grounded in source",
    )
    data = gen.model_dump()
    assert data["values"] == {"field_a": "text", "field_b": "more text"}
    assert data["confidence"] == 0.9


# --- SynthesisResultArtifact ---


def test_synthesis_result_artifact_defaults() -> None:
    artifact = SynthesisResultArtifact(
        transformation_type="issuer_payload",
        execution_id="exec_1",
        values={"field_a": "text"},
        confidence=0.9,
        rationale="rationale here",
    )
    assert artifact.synthesis_result_schema_version == "v1"


def test_synthesis_result_artifact_rejects_extra() -> None:
    with pytest.raises(ValidationError):
        SynthesisResultArtifact(  # type: ignore[call-arg]
            transformation_type="issuer_payload",
            execution_id="exec_1",
            values={},
            confidence=None,
            rationale=None,
            bad_field="nope",
        )


# --- LlmCallMeta ---


def test_llm_call_meta_optional_fields() -> None:
    meta = LlmCallMeta(provider="replay", model_id="replay", temperature=0.0)
    assert meta.input_tokens is None
    assert meta.output_tokens is None
    assert meta.latency_ms is None
    assert meta.system_prompt is None
    assert meta.user_prompt is None
