"""HTTP ingress contract: /ingest decisions, 422 on malformed, and /reset."""

from __future__ import annotations


def test_ingest_created_then_duplicate(client, skill_event):
    first = client.post("/ingest", json=skill_event())
    assert first.status_code == 200 and first.json()["status"] == "created"
    exec_id = first.json()["execution_id"]

    again = client.post("/ingest", json=skill_event(event_id="evt_1_again"))
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    assert again.json()["execution_id"] == exec_id


def test_ingest_malformed_returns_422(client, skill_event):
    bad = skill_event()
    del bad["metadata"]["event_id"]
    resp = client.post("/ingest", json=bad)
    assert resp.status_code == 422
    assert resp.json()["status"] == "rejected"


def test_reset_endpoint(client, skill_event):
    client.post("/ingest", json=skill_event())
    resp = client.post("/reset")
    assert resp.status_code == 200 and resp.json()["ok"] is True
    assert resp.json()["cleared"] >= 1


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"
