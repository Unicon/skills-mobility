"""Token endpoint tests for the Mock SmartResume — TestClient, no network."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient
from mock_smartresume.app import create_app
from mock_smartresume.config import Settings
from mock_smartresume.token_store import CANNED_TOKEN

client = TestClient(create_app(Settings()))
BASIC = "Basic " + base64.b64encode(b"cid:akey").decode()
FORM = {"grant_type": "client_credentials", "scope": "delete readonly replace"}


def test_token_happy_path_returns_canned_token() -> None:
    resp = client.post("/api/v1/token", headers={"Authorization": BASIC}, data=FORM)
    assert resp.status_code == 200
    assert resp.json() == {
        "access_token": CANNED_TOKEN,
        "token_type": "Bearer",
        "expires_in": 3600,
    }


def test_token_missing_auth_is_401() -> None:
    resp = client.post("/api/v1/token", data=FORM)
    assert resp.status_code == 401


def test_token_empty_credentials_is_401() -> None:
    empty = "Basic " + base64.b64encode(b":").decode()
    resp = client.post("/api/v1/token", headers={"Authorization": empty}, data=FORM)
    assert resp.status_code == 401


def test_token_wrong_grant_type_is_400() -> None:
    resp = client.post(
        "/api/v1/token", headers={"Authorization": BASIC}, data={"grant_type": "password"}
    )
    assert resp.status_code == 400


def test_token_missing_grant_type_is_400() -> None:
    resp = client.post("/api/v1/token", headers={"Authorization": BASIC}, data={})
    assert resp.status_code == 400
