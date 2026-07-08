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
        # Correlation ids preserved from the request in the result record (FR-LCW-11).
        "workflow_id": "wf_1",
        "execution_id": "exec_1",
        "step_id": "step_wallet",
        "correlation_id": "corr_1",
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
    # Ids preserved even on the failure path (FR-LCW-11).
    assert (body["workflow_id"], body["execution_id"], body["step_id"], body["correlation_id"]) == (
        "wf_1",
        "exec_1",
        "step_wallet",
        "corr_1",
    )


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


def test_service_env_and_token_load_regardless_of_cwd(tmp_path, monkeypatch) -> None:
    # The service .env (own port + the shared LEARNCARD_ token) must load even when the
    # process runs from a different CWD than the service dir — the repo-root-vs-service-dir
    # bug behind the empty-token "Authorization: Bearer " crash. Anchored env_file fixes it.
    from learncard_wallet_adapter.config import ENV_FILE

    for var in ("LEARNCARD_WALLET_ADAPTER_PORT", "LEARNCARD_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT the service dir
    original = ENV_FILE.read_text() if ENV_FILE.exists() else None
    ENV_FILE.write_text("LEARNCARD_WALLET_ADAPTER_PORT=8901\nLEARNCARD_API_TOKEN=tok-xyz\n")
    try:
        assert Settings().port == 8901  # service-prefixed var, own Settings
        assert LearnCardSettings(_env_file=ENV_FILE).api_token == "tok-xyz"  # shared token
    finally:
        if original is None:
            ENV_FILE.unlink()
        else:
            ENV_FILE.write_text(original)
