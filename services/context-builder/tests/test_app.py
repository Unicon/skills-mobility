"""App wiring: the factory builds, profiles load, and /healthz reports them."""

from __future__ import annotations

from context_builder.app import create_app
from fastapi.testclient import TestClient


def test_healthz_lists_loaded_profiles():
    client = TestClient(create_app())
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["profiles"]) == {"skill_mastered", "course_completed", "badge_awarded"}
