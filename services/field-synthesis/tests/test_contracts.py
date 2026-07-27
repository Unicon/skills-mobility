from field_synthesis.contracts import (
    LlmCallMeta,
    SynthesisGeneration,
    SynthesisRequest,
    SynthesisResponse,
)

_SEAM_KEYS = {
    "status",
    "synthesis_result_ref",
    "llm_invocation_log_ref",
    "values",
    "confidence",
    "rationale",
}


# --- SynthesisRequest ---


def test_synthesis_request_optional_fields_default_to_none() -> None:
    req = SynthesisRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="credential_template",
    )
    assert req.synthesis_request_ref is None
    assert req.synthesis_request is None


# --- SynthesisResponse ---


def test_response_envelope_has_exact_seam_keys() -> None:
    resp = SynthesisResponse.succeeded(
        synthesis_result_ref="synthesis_result:exec_1",
        llm_invocation_log_ref="llmcall:exec_1",
        values={"achievement_description": "You did it."},
        confidence=0.9,
        rationale="grounded in the outcome record",
    )
    assert set(resp.model_dump().keys()) == _SEAM_KEYS
    assert resp.status == "succeeded"
    assert resp.synthesis_result_ref == "synthesis_result:exec_1"
    assert resp.confidence == 0.9
    assert resp.rationale == "grounded in the outcome record"


def test_failed_response_has_none_result_ref() -> None:
    resp = SynthesisResponse.failed(llm_invocation_log_ref="llmcall:exec_1")
    assert resp.status == "failed"
    assert resp.synthesis_result_ref is None


def test_failed_response_accepts_no_log_ref() -> None:
    resp = SynthesisResponse.failed()
    assert resp.llm_invocation_log_ref is None


# --- SynthesisGeneration ---


def test_synthesis_generation_round_trip() -> None:
    gen = SynthesisGeneration(
        values={"field_a": "text", "field_b": "more text"},
        confidence=0.9,
        rationale="grounded in source",
    )
    data = gen.model_dump()
    assert data["values"] == {"field_a": "text", "field_b": "more text"}
    assert data["confidence"] == 0.9


# --- LlmCallMeta ---


def test_llm_call_meta_optional_fields() -> None:
    meta = LlmCallMeta(provider="replay", model_id="replay", temperature=0.0)
    assert meta.input_tokens is None
    assert meta.output_tokens is None
    assert meta.latency_ms is None
    assert meta.system_prompt is None
    assert meta.user_prompt is None
