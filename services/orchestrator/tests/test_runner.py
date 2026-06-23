"""The Phase-1 deterministic plan: step order, the issue→wallet chain (DID and
profile threaded through), the OBv3 stub, and the issuer-failure short-circuit."""

from __future__ import annotations

from typing import Any

from orchestrator import obv3, runner
from orchestrator.clients import StubContextBuilder, StubDeliveryRouter, StubProfileResolver
from orchestrator.schemas import RunRequest


class SpyDeliveryRouter:
    """Wraps the stub router and records the (action, payload) dispatch order."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._inner = StubDeliveryRouter()

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((action, payload))
        return self._inner.dispatch(action, payload)


def _run(event: dict[str, Any], delivery: Any = None):
    return runner.run_workflow(
        RunRequest(execution_id="exec_1", event=event),
        context_builder=StubContextBuilder(),
        profile_resolver=StubProfileResolver(),
        delivery_router=delivery or StubDeliveryRouter(),
        issuer_id="did:web:issuer.example",
    )


def test_happy_path_runs_all_steps_in_order(sample_event):
    spy = SpyDeliveryRouter()
    record = _run(sample_event, spy)
    assert record.status == "completed"
    assert [s.step for s in record.steps] == [
        "build_context",
        "resolve_profile",
        "prepare_issuer_input",
        "issue",
        "prepare_wallet_input",
        "deliver_to_wallet",
    ]
    # Issue precedes wallet delivery.
    assert [action for action, _ in spy.calls] == [
        "issue_learncard_badge",
        "deliver_to_learncard_wallet",
    ]
    # The resolved DID is embedded in the unsigned VC sent to the issuer.
    unsigned = spy.calls[0][1]["unsigned_vc"]
    assert unsigned["credentialSubject"]["id"].startswith("did:web:")
    # The issued (stub-signed) credential and resolved profile flow to wallet delivery.
    wallet = spy.calls[1][1]
    assert wallet["recipient_profile_id"].startswith("@")
    assert "proof" in wallet["signed_credential"]
    assert record.result["recipient_profile_id"].startswith("@")


class _FailingIssuer:
    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action == "issue_learncard_badge":
            return {"status": "failed", "action": action, "error": {"message": "issuer down"}}
        return {"status": "succeeded", "action": action, "result": {}}


def test_issuer_failure_short_circuits_before_wallet(sample_event):
    record = _run(sample_event, _FailingIssuer())
    assert record.status == "failed"
    steps = [s.step for s in record.steps]
    assert "issue" in steps and "deliver_to_wallet" not in steps
    assert record.steps[-1].status == "error"


def test_obv3_builder_uses_outcome_and_did():
    bundle = {
        "source_data": {
            "outcome": {"display_name": "Apply accounting", "description": "Can apply accounting."}
        }
    }
    vc = obv3.build_unsigned_obv3(bundle, "did:web:net:users:u1", "did:web:issuer")
    assert vc["credentialSubject"]["id"] == "did:web:net:users:u1"
    assert vc["credentialSubject"]["achievement"]["name"] == "Apply accounting"
    assert vc["issuer"]["id"] == "did:web:issuer"
