from delivery_targets.contracts import (
    DeliveryTarget,
    SelectionResponse,
    TargetSelection,
)

_SEAM_KEYS = {
    "status",
    "selection_artifact_ref",
    "selected_targets",
    "llm_invocation_log_ref",
}


def test_delivery_target_enum_values() -> None:
    assert DeliveryTarget.LEARNCARD_ISSUER == "learncard_issuer"
    assert DeliveryTarget.LEARNCARD_WALLET == "learncard_wallet"
    assert DeliveryTarget.SMART_RESUME == "smart_resume"


def test_response_envelope_has_exact_seam_keys() -> None:
    resp = SelectionResponse.succeeded(
        selection_artifact_ref="selection:exec_1",
        selected_targets=["learncard_issuer", "learncard_wallet"],
        llm_invocation_log_ref="llmcall:exec_1",
    )
    assert set(resp.model_dump().keys()) == _SEAM_KEYS
    assert resp.status == "succeeded"
    assert resp.selected_targets == ["learncard_issuer", "learncard_wallet"]


def test_failed_response_has_empty_selected_targets() -> None:
    resp = SelectionResponse.failed(llm_invocation_log_ref="llmcall:exec_1")
    assert resp.status == "failed"
    assert resp.selected_targets == []
    assert resp.selection_artifact_ref is None


def test_failed_response_accepts_no_log_ref() -> None:
    resp = SelectionResponse.failed()
    assert resp.llm_invocation_log_ref is None


def test_target_selection_fields() -> None:
    sel = TargetSelection(
        delivery_target="learncard_issuer",
        confidence=0.95,
        rationale="credential-enabled course",
    )
    assert sel.delivery_target == "learncard_issuer"
    assert sel.confidence == 0.95
