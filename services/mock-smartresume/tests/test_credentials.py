"""Credentials endpoint tests for the Mock SmartResume — TestClient, no network."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient
from mock_smartresume.app import create_app
from mock_smartresume.config import Settings
from mock_smartresume.token_store import CANNED_TOKEN, derive_redirect_token

client = TestClient(create_app(Settings()))
BEARER = {"Authorization": f"Bearer {CANNED_TOKEN}"}

RECIPIENT_ID = "mailto:learner@example.com"
CREDENTIAL_ID = "https://example.com/credentials/abc123"
BODY = {
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    "recipient": {"id": RECIPIENT_ID},
    "credentials": [
        {
            "id": CREDENTIAL_ID,
            "type": ["VerifiableCredential", "OpenBadgeCredential"],
            "credentialSubject": {
                "id": RECIPIENT_ID,
                "achievement": {"id": "https://example.com/achievements/finc106"},
            },
        }
    ],
}


def test_credentials_happy_path_unverified() -> None:
    resp = client.post("/api/v1/credentials", headers=BEARER, json=BODY)
    assert resp.status_code == 200
    token = derive_redirect_token(RECIPIENT_ID, CREDENTIAL_ID)
    assert resp.json() == {
        "redirect_url": f"https://mock.smartresume.example/createmyresume/{token}"
    }


def test_credentials_happy_path_verified_with_proof() -> None:
    body = deepcopy(BODY)
    body["credentials"][0]["proof"] = {"type": "Ed25519Signature2020"}  # type: ignore[index]
    resp = client.post("/api/v1/credentials", headers=BEARER, json=body)
    assert resp.status_code == 200  # proof accepted, does not change the outcome


def test_credentials_redirect_url_is_deterministic() -> None:
    a = client.post("/api/v1/credentials", headers=BEARER, json=BODY).json()
    b = client.post("/api/v1/credentials", headers=BEARER, json=BODY).json()
    assert a == b  # same inputs -> same redirect_url every run


def test_credentials_missing_bearer_is_401() -> None:
    resp = client.post("/api/v1/credentials", json=BODY)
    assert resp.status_code == 401


def test_credentials_wrong_token_is_401() -> None:
    resp = client.post(
        "/api/v1/credentials", headers={"Authorization": "Bearer nope"}, json=BODY
    )
    assert resp.status_code == 401


def test_credentials_missing_recipient_id_is_400() -> None:
    body = deepcopy(BODY)
    body["recipient"] = {}  # type: ignore[assignment]
    resp = client.post("/api/v1/credentials", headers=BEARER, json=body)
    assert resp.status_code == 400


def test_credentials_missing_credential_id_is_400() -> None:
    body = deepcopy(BODY)
    del body["credentials"][0]["id"]  # type: ignore[attr-defined]
    resp = client.post("/api/v1/credentials", headers=BEARER, json=body)
    assert resp.status_code == 400


def test_credentials_missing_achievement_id_is_400() -> None:
    body = deepcopy(BODY)
    body["credentials"][0]["credentialSubject"]["achievement"] = {}  # type: ignore[index]
    resp = client.post("/api/v1/credentials", headers=BEARER, json=body)
    assert resp.status_code == 400


def test_credentials_get_is_405() -> None:
    resp = client.get("/api/v1/credentials")
    assert resp.status_code == 405
