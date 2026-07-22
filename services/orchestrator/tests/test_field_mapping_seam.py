"""Item 8: the orchestrator calls the Field Mapping service (best-effort)."""

from typing import Any

from orchestrator.actions import (
    ActionDeps,
    _generate_payload_mapping,
    _mapping_source_payloads,
)
from orchestrator.clients import EnvelopeContext, StubDeliveryRouter, StubProfileResolver

_ENV = EnvelopeContext(
    workflow_id="e1", execution_id="e1", correlation_id="c1", delivery_config_ref="cfg"
)


class _SpyFieldMapping:
    def __init__(self, result: dict[str, Any] | None = None, raise_exc: bool = False) -> None:
        self.result = result
        self.raise_exc = raise_exc
        self.last_request: dict[str, Any] | None = None

    def map(self, request: dict[str, Any], ctx: EnvelopeContext, step_id: str) -> dict[str, Any]:
        self.last_request = request
        if self.raise_exc:
            raise RuntimeError("field mapping unreachable")
        assert self.result is not None
        return self.result


def _deps(field_mapping: Any) -> ActionDeps:
    return ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=field_mapping,
        issuer_id="did:web:issuer",
        envelope=_ENV,
    )


_PROFILE = {"did": "did:web:network.learncard.com:users:learner", "profile_id": "@learner"}
_ISSUER_INPUTS = {
    "transformation_type": "issuer_payload",
    "delivery_target": "learncard_issuer",
    "synthesis_allowed": True,
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "bundle": {"source_data": {"outcome": {"display_name": "X"}}},
    "issuer_id": "did:web:issuer",
    "resolved_profile": _PROFILE,
}
_WALLET_INPUTS = {
    "transformation_type": "wallet_payload",
    "delivery_target": "learncard_wallet",
    "synthesis_allowed": False,
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "issued": {"result": {"issued_credential": {"proof": {"type": "x"}}}},
    "resolved_profile": _PROFILE,
}

_OK = {
    "status": "succeeded",
    "mapping_artifact_ref": "mapping:1",
    "synthesis_request_ref": "synthesis:1",
    "requires_synthesis": True,
    "llm_invocation_log_ref": "llmcall:1",
}


def test_issuer_source_payloads_carry_source_data_and_profile() -> None:
    sp = _mapping_source_payloads(_ISSUER_INPUTS)
    assert sp["outcome"] == {"display_name": "X"}
    assert sp["profile_resolution"] == {
        "recipient_did": _PROFILE["did"],
        "recipient_profile_id": "@learner",
        "issuer_id": "did:web:issuer",
    }


def test_wallet_source_payloads_carry_issued_badge_and_profile() -> None:
    sp = _mapping_source_payloads(_WALLET_INPUTS)
    assert sp["issued_badge"] == {"proof": {"type": "x"}}
    assert sp["profile_resolution"]["recipient_profile_id"] == "@learner"


def test_returns_service_refs_on_success() -> None:
    fm = _SpyFieldMapping(result=_OK)
    out = _generate_payload_mapping(_ISSUER_INPUTS, _deps(fm))
    assert out["mapping_artifact_ref"] == "mapping:1"
    assert out["requires_synthesis"] is True
    assert fm.last_request is not None
    assert fm.last_request["transformation_type"] == "issuer_payload"
    assert "profile_resolution" in fm.last_request["source_payloads"]


def test_transport_failure_is_non_fatal_and_degrades() -> None:
    out = _generate_payload_mapping(_WALLET_INPUTS, _deps(_SpyFieldMapping(raise_exc=True)))
    assert out["status"] == "succeeded"  # non-fatal: obv3 stand-in still delivers
    assert out["mapping_artifact_ref"] is None


def test_service_failed_status_is_non_fatal() -> None:
    failed = {**_OK, "status": "failed", "mapping_artifact_ref": None}
    out = _generate_payload_mapping(_ISSUER_INPUTS, _deps(_SpyFieldMapping(result=failed)))
    assert out["status"] == "succeeded"
    assert out["mapping_artifact_ref"] is None
