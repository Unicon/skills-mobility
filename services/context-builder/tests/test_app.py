"""App wiring + the HTTP layer of POST /build-context (Pydantic validation,
response shape) — concerns not covered by the builder-level tests."""

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


def _client_with_fake_lms(fake_client, responses):
    app = create_app()
    app.state.lms_client = fake_client(responses)  # avoid touching the network
    return TestClient(app)


def test_build_context_happy_path(fake_client):
    # badge_awarded is the simplest profile (two fetches), enough for the HTTP path.
    client = _client_with_fake_lms(
        fake_client,
        {"/api/v1/badges/B1": (200, {"id": "B1"}), "/api/v1/users/U1/profile": (200, {"id": "U1"})},
    )
    r = client.post(
        "/build-context",
        json={
            "execution_id": "wf_1",
            "event": {
                "metadata": {"event_name": "badge_awarded"},
                "body": {"badge_id": "B1", "user_id": "U1"},
            },
        },
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert body["event_type"] == "badge_awarded"
    assert body["source_data"]["badge"]["id"] == "B1"
    assert body["source_data"]["user_profile"]["id"] == "U1"


def test_build_context_malformed_request_is_422(fake_client):
    client = _client_with_fake_lms(fake_client, {})
    # Missing the required `event` field → Pydantic rejects before any fetch.
    r = client.post("/build-context", json={"execution_id": "wf_1"})
    assert r.status_code == 422
