"""HTTP contract: run a workflow, then read back the persisted execution record."""

from __future__ import annotations


def test_run_workflow_completes_and_persists(client, sample_event):
    resp = client.post("/run-workflow", json={"execution_id": "exec_42", "event": sample_event})
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_id"] == "exec_42"
    assert body["status"] == "completed"
    assert [s["step"] for s in body["steps"]][0] == "build_context"

    got = client.get("/executions/exec_42")
    assert got.status_code == 200
    assert got.json()["status"] == "completed"


def test_unknown_execution_returns_404(client):
    assert client.get("/executions/nope").status_code == 404


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"
