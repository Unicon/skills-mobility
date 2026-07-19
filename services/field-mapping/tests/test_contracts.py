from typing import Any

import pytest
from field_mapping.contracts import (
    DeliveryTarget,
    MappingRequest,
    MappingResponse,
    TransformationType,
)
from pydantic import ValidationError

# The exact envelope the Orchestrator mapping seam reads (actions.py) plus the
# inline JSONata the Transformation Executor seam uses.
_SEAM_KEYS = {
    "status",
    "mapping_artifact_ref",
    "synthesis_request_ref",
    "requires_synthesis",
    "llm_invocation_log_ref",
    "mapping",
}


def _base(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "execution_id": "exec_1",
        "event_id": "evt_1",
        "transformation_type": "issuer_payload",
        "source_system": "mock_lms",
        "fetch_profile_id": "skill_mastered.v1",
        "delivery_target": "learncard_issuer",
        "synthesis_allowed": True,
        "source_payloads": {"learner_context": {}},
    }
    data.update(overrides)
    return data


def test_request_accepts_all_transformation_types() -> None:
    issuer = MappingRequest(**_base(transformation_type="issuer_payload"))
    wallet = MappingRequest(
        **_base(transformation_type="wallet_payload", delivery_target="learncard_wallet")
    )
    template = _base(transformation_type="credential_template")
    del template["delivery_target"]  # credential_template omits it entirely
    tmpl = MappingRequest(**template)

    assert issuer.transformation_type is TransformationType.ISSUER_PAYLOAD
    assert wallet.delivery_target is DeliveryTarget.LEARNCARD_WALLET
    assert tmpl.delivery_target is None


def test_credential_template_rejects_delivery_target() -> None:
    data = _base(transformation_type="credential_template", delivery_target="learncard_issuer")
    with pytest.raises(ValidationError):
        MappingRequest(**data)


def test_issuer_and_wallet_require_delivery_target() -> None:
    for tt in ("issuer_payload", "wallet_payload"):
        data = _base(transformation_type=tt)
        del data["delivery_target"]
        with pytest.raises(ValidationError):
            MappingRequest(**data)


def test_response_envelope_has_exact_seam_keys() -> None:
    resp = MappingResponse.succeeded(
        mapping_artifact_ref="mapping:1",
        synthesis_request_ref="synthesis:1",
        llm_invocation_log_ref="llmcall:1",
        synthesis_allowed=True,
        placeholder_ids=["achievement_description"],
        mapping='{"id": source_payloads.profile_resolution.recipient_did}',
    )
    assert set(resp.model_dump().keys()) == _SEAM_KEYS
    assert resp.requires_synthesis is True
    assert resp.mapping == '{"id": source_payloads.profile_resolution.recipient_did}'


def test_response_mapping_is_none_when_not_passed() -> None:
    resp = MappingResponse.succeeded(
        mapping_artifact_ref="mapping:1",
        synthesis_request_ref=None,
        llm_invocation_log_ref="llmcall:1",
        synthesis_allowed=False,
        placeholder_ids=[],
    )
    assert resp.mapping is None


def test_failed_response_mapping_is_none() -> None:
    resp = MappingResponse.failed(llm_invocation_log_ref="llmcall:1")
    assert resp.mapping is None


def test_requires_synthesis_derived_never_true_when_synthesis_forbidden() -> None:
    # Placeholders + a ref present, but synthesis was forbidden -> still False (§6/§10).
    resp = MappingResponse.succeeded(
        mapping_artifact_ref="mapping:1",
        synthesis_request_ref="synthesis:1",
        llm_invocation_log_ref="llmcall:1",
        synthesis_allowed=False,
        placeholder_ids=["achievement_description"],
    )
    assert resp.requires_synthesis is False
