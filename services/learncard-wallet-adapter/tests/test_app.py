"""API tests for the LearnCard Wallet Adapter — no network (MockTransport)."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy

import httpx
from fastapi.testclient import TestClient
from learncard_api import LearnCardClient, LearnCardSettings
from learncard_wallet_adapter.app import create_app
from learncard_wallet_adapter.config import Settings

ENDPOINT = "/internal/deliver-to-learncard-wallet"
CREDENTIAL_URI = "lc:network:network.learncard.com/trpc:credential:abc-123"

REQUEST = {
    "contract_version": "v1",
    "workflow_id": "wf_1",
    "execution_id": "exec_1",
    "step_id": "step_wallet",
    "correlation_id": "corr_1",
    "delivery_config_ref": "learncard-dev",
    "payload": {
        "recipient_profile_id": "smi-learner-1",
        "signed_credential": {"type": ["VerifiableCredential"], "proof": {}},
    },
}


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    lc = LearnCardClient(
        LearnCardSettings(api_url="https://net.example/api", api_token="tok-123"),
        transport=httpx.MockTransport(handler),
    )
    return TestClient(create_app(Settings(), lc))


def test_deliver_success_normalizes_and_sends_expected_call() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=CREDENTIAL_URI)

    resp = _client(handle).post(ENDPOINT, json=REQUEST)

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "succeeded",
        "external_reference_id": CREDENTIAL_URI,
        "result": {"delivery_state": "accepted"},
        "error": None,
    }
    # Contract: pre-signed VC delivered to the recipient's profile path.
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/api/credential/send/smi-learner-1"
    assert json.loads(seen[0].content) == {
        "credential": {"type": ["VerifiableCredential"], "proof": {}}
    }


def test_learncard_error_is_normalized_to_failed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    resp = _client(handle).post(ENDPOINT, json=REQUEST)

    assert resp.status_code == 200  # adapter normalizes; never leaks the vendor error
    body = resp.json()
    assert body["status"] == "failed"
    assert body["external_reference_id"] is None
    assert body["result"] is None
    assert body["error"]["message"]  # a message is present


def test_missing_recipient_profile_id_is_422() -> None:
    def handle(request: httpx.Request) -> httpx.Response:  # should never be called
        raise AssertionError("delivery attempted despite missing recipient_profile_id")

    bad = deepcopy(REQUEST)
    del bad["payload"]["recipient_profile_id"]  # type: ignore[attr-defined]

    resp = _client(handle).post(ENDPOINT, json=bad)
    assert resp.status_code == 422


def test_healthz() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=CREDENTIAL_URI)

    resp = _client(handle).get("/healthz")
    assert resp.json() == {"status": "ok"}


# --- read-back (#53) ---

READBACK = "/internal/delivered-credential"


def _readback_client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    """Inject a recipient client (read token) driving the read-back; the sender
    client must not be touched during a read-back."""
    def _no_send(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"unexpected sender call: {request.url}")

    sender = LearnCardClient(
        LearnCardSettings(api_url="https://net.example/api", api_token="send"),
        transport=httpx.MockTransport(_no_send),
    )
    recipient = LearnCardClient(
        LearnCardSettings(api_url="https://net.example/api", api_token="recip"),
        transport=httpx.MockTransport(handler),
    )
    return TestClient(create_app(Settings(), sender, recipient))


def test_read_back_delivered_resolves_the_vc() -> None:
    vc = {"type": ["VerifiableCredential"], "credentialSubject": {"id": "did:web:x:learner"}}
    sent = "2026-07-01T02:32:23.023Z"
    incoming = [
        {"uri": "lc:other", "to": "smi-demo-learner", "from": "x", "sent": sent},
        {"uri": CREDENTIAL_URI, "to": "smi-demo-learner", "from": "smi-demo-issuer", "sent": sent},
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/credentials/incoming"):
            return httpx.Response(200, json=incoming)
        if request.url.path.endswith("/storage/resolve"):
            assert request.url.params["uri"] == CREDENTIAL_URI
            return httpx.Response(200, json=vc)
        raise AssertionError(f"unexpected path {request.url.path}")

    body = _readback_client(handle).get(READBACK, params={"uri": CREDENTIAL_URI}).json()
    assert body == {
        "delivered": True,
        "recipient_profile_id": "smi-demo-learner",
        "sent_at": sent,
        "credential": vc,
        "error": None,
    }


def test_read_back_not_found_does_not_resolve() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/credentials/incoming"):
            return httpx.Response(200, json=[])
        raise AssertionError("resolve must not run when the uri is absent")

    body = _readback_client(handle).get(READBACK, params={"uri": CREDENTIAL_URI}).json()
    assert body["delivered"] is False
    assert body["credential"] is None


def test_read_back_error_is_normalized() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    resp = _readback_client(handle).get(READBACK, params={"uri": CREDENTIAL_URI})
    assert resp.status_code == 200  # never leaks the vendor error
    body = resp.json()
    assert body["delivered"] is False
    assert body["error"]
