"""HTTP contract: run a workflow (planner + executor), read back the correlated
view, exercise both supported event types, and the plan-admin endpoints."""

from __future__ import annotations

from orchestrator.app import create_app
from orchestrator.clients import (
    HttpDeliveryRouterClient,
    HttpProfileResolverClient,
    StubDeliveryRouter,
    StubProfileResolver,
)
from orchestrator.config import Settings


def test_seams_default_to_stubs_without_urls():
    app = create_app(Settings(db_path=":memory:"))
    assert isinstance(app.state.profile_resolver, StubProfileResolver)
    assert isinstance(app.state.delivery_router, StubDeliveryRouter)


def test_seams_use_http_clients_when_urls_set():
    app = create_app(
        Settings(
            db_path=":memory:",
            profile_resolver_url="http://profile-resolver:8600",
            delivery_router_url="http://delivery-router:8800",
        )
    )
    assert isinstance(app.state.profile_resolver, HttpProfileResolverClient)
    assert isinstance(app.state.delivery_router, HttpDeliveryRouterClient)


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
    # Read-model fields the Admin UI needs (#28 G3/G4): correlation id + timestamps.
    assert body["correlation_id"] == "corr_1"
    assert body["created_at"] and body["updated_at"]

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
    assert client.put("/admin/plan-lookup-toggle", json={"enabled": True}).json() == {
        "reusable_plan_lookup_enabled": True
    }
    assert client.delete("/admin/plans/phase1-skill_mastered.v1").json() == {"deleted": True}
    # Second delete is a no-op (already gone).
    assert client.delete("/admin/plans/phase1-skill_mastered.v1").json() == {"deleted": False}


def test_unknown_execution_returns_404(client):
    assert client.get("/executions/nope").status_code == 404


def test_healthz(client):
    assert client.get("/healthz").json()["status"] == "ok"


def test_settings_load_from_service_dotenv_regardless_of_cwd(tmp_path, monkeypatch):
    # The service .env must load even when the process runs from a different CWD than
    # the service dir (the repo-root-vs-service-dir bug). Covers a normal-prefixed var
    # and a LEARNCARD_-aliased one. A bare env_file=".env" would fail from tmp_path.
    from orchestrator.config import ENV_FILE

    for var in ("ORCHESTRATOR_DB_PATH", "LEARNCARD_DEMO_RECIPIENT_PROFILE_ID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT the service dir
    original = ENV_FILE.read_text() if ENV_FILE.exists() else None
    ENV_FILE.write_text("ORCHESTRATOR_DB_PATH=:memory:\nLEARNCARD_DEMO_RECIPIENT_PROFILE_ID=@demo\n")
    try:
        s = Settings()
        assert s.db_path == ":memory:"
        assert s.demo_recipient_profile_id == "@demo"  # validation_alias, LEARNCARD_-prefixed
    finally:
        if original is None:
            ENV_FILE.unlink()
        else:
            ENV_FILE.write_text(original)
