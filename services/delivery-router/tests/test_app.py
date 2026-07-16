"""API tests for the Delivery Router — adapters stubbed at the boundary."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
from delivery_router.app import create_app
from delivery_router.clients import AdapterClient
from delivery_router.config import Settings
from fastapi.testclient import TestClient

ENDPOINT = "/delivery-actions"
ISSUER_URL = "http://issuer.test"
WALLET_URL = "http://wallet.test"
SMARTRESUME_URL = "http://smartresume.test"

# (action, adapter_key) pairs
WALLET = ("deliver_to_learncard_wallet", "learncard_wallet")
ISSUER = ("issue_learncard_badge", "learncard_issuer")
SMARTRESUME = ("deliver_to_smartresume", "smart_resume")
PAYLOAD = {"recipient_profile_id": "smi-demo-learner", "signed_credential": {"x": 1}}


def _app(
    handler: Callable[[httpx.Request], httpx.Response], *, retry_limit: int = 1
) -> TestClient:
    settings = Settings(
        learncard_issuer_url=ISSUER_URL,
        learncard_wallet_url=WALLET_URL,
        smartresume_url=SMARTRESUME_URL,
    )
    client = AdapterClient(retry_limit=retry_limit, transport=httpx.MockTransport(handler))
    return TestClient(create_app(settings, client))


def _request(action: str, adapter_key: str) -> dict[str, object]:
    return {
        "action": action,
        "contract_version": "v1",
        "adapter_key": adapter_key,
        "workflow_id": "wf_1",
        "execution_id": "exec_1",
        "step_id": "step_1",
        "correlation_id": "corr_1",
        "delivery_config_ref": "learncard-dev",
        "payload": PAYLOAD,
    }


def test_wallet_dispatch_forwards_envelope_and_normalizes() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "external_reference_id": "lc:network:cred:1",
                "result": {"delivery_state": "accepted"},
                "error": None,
            },
        )

    body = _app(handle).post(ENDPOINT, json=_request(*WALLET)).json()

    assert body == {
        "status": "succeeded",
        "adapter_key": "learncard_wallet",
        "action": "deliver_to_learncard_wallet",
        "external_reference_id": "lc:network:cred:1",
        "result": {"delivery_state": "accepted"},
        "error": None,
    }
    # Routed to the wallet adapter's endpoint with the envelope forwarded (no action/adapter_key).
    assert str(seen[0].url) == f"{WALLET_URL}/internal/deliver-to-learncard-wallet"
    forwarded = json.loads(seen[0].content)
    assert "action" not in forwarded and "adapter_key" not in forwarded
    assert forwarded["delivery_config_ref"] == "learncard-dev"
    assert forwarded["payload"] == PAYLOAD


def test_issuer_dispatch_routes_to_issuer() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "succeeded", "external_reference_id": "vc_1"})

    body = _app(handle).post(ENDPOINT, json=_request(*ISSUER)).json()
    assert body["status"] == "succeeded"
    assert body["adapter_key"] == "learncard_issuer"
    assert str(seen[0].url) == f"{ISSUER_URL}/internal/issue-learncard-badge"


def test_smartresume_dispatch_routes_to_smartresume() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "external_reference_id": "https://my.smartresume.com/createmyresume/abc",
            },
        )

    body = _app(handle).post(ENDPOINT, json=_request(*SMARTRESUME)).json()
    assert body["status"] == "succeeded"
    assert body["adapter_key"] == "smart_resume"
    assert body["action"] == "deliver_to_smartresume"
    assert str(seen[0].url) == f"{SMARTRESUME_URL}/internal/deliver-to-smartresume"


def test_adapter_failure_is_passed_through() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"status": "failed", "error": {"message": "vendor said no"}}
        )

    body = _app(handle).post(ENDPOINT, json=_request(*WALLET)).json()
    assert body["status"] == "failed"
    assert body["error"] == {"message": "vendor said no"}  # structured, not flattened


def test_unconfigured_adapter_fails_cleanly() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not dispatch when the adapter URL is unset")

    settings = Settings(learncard_issuer_url=None, learncard_wallet_url=None)
    client = AdapterClient(transport=httpx.MockTransport(handle))
    tc = TestClient(create_app(settings, client))

    body = tc.post(ENDPOINT, json=_request(*WALLET)).json()
    assert body["status"] == "failed"
    assert "learncard_wallet" in body["error"]["message"]


def test_transport_error_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"status": "succeeded", "external_reference_id": "r"})

    body = _app(handle, retry_limit=1).post(ENDPOINT, json=_request(*WALLET)).json()
    assert body["status"] == "succeeded"
    assert calls["n"] == 2  # one retry


def test_unknown_action_is_422() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not dispatch an invalid action")

    # A value that will never be a real action (must not collide with a registered one).
    resp = _app(handle).post(ENDPOINT, json=_request("bogus_action", "learncard_wallet"))
    assert resp.status_code == 422


def test_healthz() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "succeeded"})

    assert _app(handle).get("/healthz").json() == {"status": "ok"}


def test_transport_error_exhausts_retries_and_normalizes_to_failed() -> None:
    # Adapter down for the whole retry window: must normalize to failed, not raise.
    calls = {"n": 0}

    def handle(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ConnectError("connection refused", request=request)

    body = _app(handle, retry_limit=1).post(ENDPOINT, json=_request(*WALLET)).json()
    assert body["status"] == "failed"  # normalized, not an unhandled exception
    assert body["adapter_key"] == "learncard_wallet"
    assert calls["n"] == 2  # first try + one retry, both failed


def test_action_is_authoritative_over_declared_adapter_key() -> None:
    # action=ISSUE routes to the issuer adapter even though the caller mis-declares
    # the wallet adapter; the response echoes the *resolved* adapter (design §5).
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"status": "succeeded", "external_reference_id": "vc_1"})

    resp = _app(handle).post(ENDPOINT, json=_request("issue_learncard_badge", "learncard_wallet"))
    body = resp.json()
    assert str(seen[0].url) == f"{ISSUER_URL}/internal/issue-learncard-badge"
    assert body["adapter_key"] == "learncard_issuer"  # resolved from action, not the declared key
    assert body["status"] == "succeeded"


def test_settings_read_from_dotenv_regardless_of_cwd(tmp_path, monkeypatch) -> None:
    # The .env lives at the service package root; Settings must load it even when the
    # process runs from a *different* CWD (the repo-root-vs-service-dir bug). A bare
    # env_file=".env" would resolve against CWD and this would fail from tmp_path.
    from delivery_router.config import _ENV_FILE

    monkeypatch.delenv("DELIVERY_ROUTER_LEARNCARD_ISSUER_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT where the .env lives
    original = _ENV_FILE.read_text() if _ENV_FILE.exists() else None
    _ENV_FILE.write_text("DELIVERY_ROUTER_LEARNCARD_ISSUER_URL=http://issuer.example\n")
    try:
        assert Settings().learncard_issuer_url == "http://issuer.example"
    finally:
        if original is None:
            _ENV_FILE.unlink()
        else:
            _ENV_FILE.write_text(original)
