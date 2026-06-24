"""HTTP contract: run a workflow (planner + executor), read back the correlated
view, exercise both supported event types, and the plan-admin endpoints."""

from __future__ import annotations


def test_run_workflow_completes_and_persists(client, sample_event):
    resp = client.post("/run-workflow", json={"execution_id": "exec_42", "event": sample_event})
    assert resp.status_code == 200
    body = resp.json()
    assert body["execution_id"] == "exec_42"
    assert body["status"] == "completed"
    assert body["event_type"] == "skill_mastered"
    assert body["gate_decision"]["decision"] == "continue_to_delivery_targets"
    assert body["plan_id"] == "phase1-skill_mastered.v1"
    assert [s["action_id"] for s in body["steps"]][0] == "resolve_learncard_profile"
    assert len(body["steps"]) == 8
    assert all(s["status"] == "succeeded" for s in body["steps"])
    assert body["result"]["recipient_profile_id"].startswith("@")

    got = client.get("/executions/exec_42")
    assert got.status_code == 200
    assert got.json()["status"] == "completed"


def test_course_completed_path_completes(client, course_event):
    resp = client.post("/run-workflow", json={"execution_id": "exec_cc", "event": course_event})
    body = resp.json()
    assert body["status"] == "completed"
    assert body["event_type"] == "course_completed"
    assert body["plan_id"] == "phase1-course_completed.v1"


def test_plan_lookup_toggle_and_delete(client, sample_event):
    # A run persists the reusable delivery-phase plan.
    client.post("/run-workflow", json={"execution_id": "exec_p", "event": sample_event})
    assert client.post("/admin/plan-lookup", json={"enabled": True}).json() == {
        "reusable_plan_lookup_enabled": True
    }
    assert client.delete("/admin/plans/phase1-skill_mastered.v1").json() == {"deleted": True}
    # Second delete is a no-op (already gone).
    assert client.delete("/admin/plans/phase1-skill_mastered.v1").json() == {"deleted": False}


def test_unknown_execution_returns_404(client):
    assert client.get("/executions/nope").status_code == 404


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"
