"""API tests for the SmartResume Adapter — no network (MockTransport)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from copy import deepcopy

import httpx
from fastapi.testclient import TestClient
from smartresume_adapter.app import create_app
from smartresume_adapter.config import Settings

ENDPOINT = "/internal/deliver-to-smartresume"
API_URL = "https://sr.test"
TOKEN = "sr-token-abc"
REDIRECT_URL = "https://my.smartresume.com/createmyresume/deadbeef"

REQUEST = {
    "contract_version": "v1",
    "workflow_id": "wf_1",
    "execution_id": "exec_1",
    "step_id": "step_smartresume",
    "correlation_id": "corr_1",
    "delivery_config_ref": "smartresume-staging",
    "payload": {
        "recipient": {
            "id": "mailto:learner@example.com",
            "givenName": "Ada",
            "familyName": "Lovelace",
            "email": "learner@example.com",
        },
        "credentials": [
            {
                "id": "https://example.com/credentials/abc123",
                "type": ["VerifiableCredential", "OpenBadgeCredential"],
                "name": "Introduction to Finance",
                "credentialSubject": {
                    "id": "mailto:learner@example.com",
                    "achievement": {
                        "id": "https://example.com/achievements/finc106",
                        "achievementType": "Course",
                        "name": "Introduction to Finance",
                    },
                },
                "issuer": {"id": "https://example.com/issuers/wasatch"},
            }
        ],
    },
}


def _client(
    credentials_response: Callable[[httpx.Request], httpx.Response],
    seen: list[httpx.Request] | None = None,
    *,
    client_id: str = "cid",
    access_key: str = "akey",
) -> TestClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if request.url.path == "/api/v1/token":
            return httpx.Response(
                200, json={"access_token": TOKEN, "token_type": "Bearer", "expires_in": 3600}
            )
        return credentials_response(request)

    hx = httpx.Client(transport=httpx.MockTransport(handle))
    settings = Settings(api_url=API_URL, client_id=client_id, access_key=access_key)
    return TestClient(create_app(settings, hx))


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"redirect_url": REDIRECT_URL})


def test_deliver_success_normalizes_and_sends_expected_call() -> None:
    seen: list[httpx.Request] = []
    resp = _client(_ok, seen).post(ENDPOINT, json=REQUEST)

    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "status": "succeeded",
        "workflow_id": "wf_1",
        "execution_id": "exec_1",
        "step_id": "step_smartresume",
        "correlation_id": "corr_1",
        "external_reference_id": REDIRECT_URL,
        "result": {"redirect_url": REDIRECT_URL},
        "error": None,
    }

    token_req, cred_req = seen[0], seen[1]
    # Token exchange: Basic auth, form body, client_credentials grant.
    assert token_req.method == "POST"
    assert token_req.url.path == "/api/v1/token"
    expected_basic = base64.b64encode(b"cid:akey").decode()
    assert token_req.headers["authorization"] == f"Basic {expected_basic}"
    assert token_req.content == b"grant_type=client_credentials&scope=delete+readonly+replace"

    # Delivery: Bearer token from the exchange + assembled body.
    assert cred_req.method == "POST"
    assert cred_req.url.path == "/api/v1/credentials"
    assert cred_req.headers["authorization"] == f"Bearer {TOKEN}"
    sent = json.loads(cred_req.content)
    assert sent["@context"] == [
        "https://www.w3.org/2018/credentials/v1",
        "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
    ]
    assert sent["recipient"] == {
        "id": "mailto:learner@example.com",
        "givenName": "Ada",
        "familyName": "Lovelace",
        "email": "learner@example.com",
    }
    assert len(sent["credentials"]) == 1
    assert "proof" not in sent["credentials"][0]  # unverified path
    assert "recipienttoken" not in sent  # not supplied


def test_proof_passed_through_when_present() -> None:
    seen: list[httpx.Request] = []
    req = deepcopy(REQUEST)
    req["payload"]["credentials"][0]["proof"] = {"type": "Ed25519Signature2020"}  # type: ignore[index]

    _client(_ok, seen).post(ENDPOINT, json=req)

    sent = json.loads(seen[1].content)
    assert sent["credentials"][0]["proof"] == {"type": "Ed25519Signature2020"}


def test_recipienttoken_forwarded_when_present() -> None:
    seen: list[httpx.Request] = []
    req = deepcopy(REQUEST)
    req["payload"]["recipienttoken"] = "rt-123"  # type: ignore[index]

    _client(_ok, seen).post(ENDPOINT, json=req)

    sent = json.loads(seen[1].content)
    assert sent["recipienttoken"] == "rt-123"


def test_target_name_truncated_to_40_chars() -> None:
    seen: list[httpx.Request] = []
    req = deepcopy(REQUEST)
    long_name = "x" * 60
    req["payload"]["credentials"][0]["credentialSubject"]["achievement"]["alignment"] = [  # type: ignore[index]
        {"targetName": long_name, "targetType": "Competency"}
    ]

    _client(_ok, seen).post(ENDPOINT, json=req)

    sent = json.loads(seen[1].content)
    aligned = sent["credentials"][0]["credentialSubject"]["achievement"]["alignment"][0]
    assert aligned["targetName"] == "x" * 40


def test_unauthorized_is_normalized_to_failed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    resp = _client(handle).post(ENDPOINT, json=REQUEST)

    assert resp.status_code == 200  # adapter normalizes; never leaks the vendor error
    body = resp.json()
    assert body["status"] == "failed"
    assert body["external_reference_id"] is None
    assert body["result"] is None
    assert body["error"]["http_status"] == 401
    assert body["error"]["body"] == {"message": "Unauthorized"}
    # Ids preserved even on the failure path (FR-SR-12).
    assert (
        body["workflow_id"],
        body["execution_id"],
        body["step_id"],
        body["correlation_id"],
    ) == ("wf_1", "exec_1", "step_smartresume", "corr_1")


def test_bad_request_is_normalized_to_failed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "missing recipient.id"})

    body = _client(handle).post(ENDPOINT, json=REQUEST).json()
    assert body["status"] == "failed"
    assert body["error"]["http_status"] == 400
    assert body["error"]["body"] == {"error": "missing recipient.id"}


def test_server_error_is_normalized_to_failed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    body = _client(handle).post(ENDPOINT, json=REQUEST).json()
    assert body["status"] == "failed"
    assert body["error"]["http_status"] == 500


def test_token_failure_is_normalized_to_failed() -> None:
    # A failing /token call (TokenError) must normalize exactly like a
    # /credentials failure — never leak, never 500.
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/token"  # never reaches /credentials
        return httpx.Response(401, json={"message": "bad client credentials"})

    hx = httpx.Client(transport=httpx.MockTransport(handle))
    settings = Settings(api_url=API_URL, client_id="cid", access_key="wrong")
    resp = TestClient(create_app(settings, hx)).post(ENDPOINT, json=REQUEST)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["external_reference_id"] is None
    assert "token exchange failed with HTTP 401" in body["error"]["message"]
    # Ids preserved on the token-failure path too (FR-SR-12).
    assert (
        body["workflow_id"],
        body["execution_id"],
        body["step_id"],
        body["correlation_id"],
    ) == ("wf_1", "exec_1", "step_smartresume", "corr_1")


def test_missing_recipient_is_422() -> None:
    bad = deepcopy(REQUEST)
    del bad["payload"]["recipient"]  # type: ignore[attr-defined]

    resp = _client(_ok).post(ENDPOINT, json=bad)
    assert resp.status_code == 422


def test_healthz() -> None:
    resp = _client(_ok).get("/healthz")
    assert resp.json() == {"status": "ok"}
