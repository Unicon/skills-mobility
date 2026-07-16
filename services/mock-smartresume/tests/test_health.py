"""Health endpoint tests for the Mock SmartResume."""

from __future__ import annotations

from fastapi.testclient import TestClient
from mock_smartresume.app import create_app
from mock_smartresume.config import Settings

client = TestClient(create_app(Settings()))


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unknown_route_is_404() -> None:
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
