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
    assert [d["kind"] for d in body["decisions"]] == [
        "gate",
        "delivery_targets",
        "workflow_actions_plan",
    ]
    gate_decision, targets_decision, plan_decision = body["decisions"]
    assert gate_decision == {
        "kind": "gate",
        "confidence": None,
        "rationale": "Deterministic Phase 1 happy-path gate decision.",
        "outcome": "continue_to_delivery_targets",
        "candidates": [],
        "artifact_ref": None,
        "invocation_log_ref": None,
        "created_at": gate_decision["created_at"],
    }
    # Neither Delivery Targets nor Workflow Actions is configured in tests, so both
    # fall back to the deterministic stubs (best-effort seams, #79).
    assert targets_decision == {
        "kind": "delivery_targets",
        "confidence": None,
        "rationale": "",
        "outcome": "learncard_issuer, learncard_wallet",
        "candidates": [],
        "artifact_ref": None,
        "invocation_log_ref": None,
        "created_at": targets_decision["created_at"],
    }
    assert plan_decision == {
        "kind": "workflow_actions_plan",
        "confidence": None,
        "rationale": "Deterministic Phase 1 LearnCard workflow.",
        "outcome": "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1",
        "candidates": [],
        "artifact_ref": None,
        "invocation_log_ref": None,
        "created_at": plan_decision["created_at"],
    }
    assert body["plan_id"] == "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
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


def test_run_workflow_terminate_gate_persists_decision(client):
    # An unsupported event type: the pre-target gate terminates before delivery,
    # but the `decisions` array still records the gate outcome (#28, ADR-0007).
    event = {"metadata": {"event_name": "badge_awarded", "user_id": "U1"}, "body": {}}
    resp = client.post("/run-workflow", json={"execution_id": "exec_term", "event": event})
    body = resp.json()
    assert body["status"] == "completed"
    assert body["decisions"] == [
        {
            "kind": "gate",
            "confidence": None,
            "rationale": "Unsupported event type for Phase 1: badge_awarded.",
            "outcome": "terminate",
            "candidates": [],
            "artifact_ref": None,
            "invocation_log_ref": None,
            "created_at": body["decisions"][0]["created_at"],
        }
    ]
    assert body["plan_id"] is None


def test_course_completed_path_completes(client, course_event):
    resp = client.post("/run-workflow", json={"execution_id": "exec_cc", "event": course_event})
    body = resp.json()
    assert body["status"] == "completed"
    assert body["event_type"] == "course_completed"
    assert body["plan_id"] == "phase1-course_completed.learncard_issuer.learncard_wallet.v1"


def test_plan_lookup_toggle_and_delete(client, sample_event):
    # A run persists the reusable delivery-phase plan.
    client.post("/run-workflow", json={"execution_id": "exec_p", "event": sample_event})
    assert client.put("/admin/plan-lookup-toggle", json={"enabled": True}).json() == {
        "reusable_plan_lookup_enabled": True
    }
    plan_id = "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
    assert client.delete(f"/admin/plans/{plan_id}").json() == {"deleted": True}
    # Second delete is a no-op (already gone).
    assert client.delete(f"/admin/plans/{plan_id}").json() == {"deleted": False}


def test_list_executions_and_correlation_filter(client, sample_event, course_event):
    # Two runs with distinct correlation ids (corr_1 on skill, corr_2 on course).
    client.post("/run-workflow", json={"execution_id": "exec_a", "event": sample_event})
    client.post("/run-workflow", json={"execution_id": "exec_b", "event": course_event})

    rows = client.get("/executions").json()
    assert {r["execution_id"] for r in rows} == {"exec_a", "exec_b"}
    # Summary rows carry the Admin-UI fields incl. server-computed step progress.
    a = next(r for r in rows if r["execution_id"] == "exec_a")
    assert a["correlation_id"] == "corr_1"
    assert a["status"] == "completed"
    assert a["step_progress"] == {"completed": 8, "total": 8}
    assert a["created_at"] and a["updated_at"]
    assert "steps" not in a and "result" not in a  # compact projection

    # Correlation filter returns just that Action run's executions (#28 G2).
    filtered = client.get("/executions", params={"correlation_id": "corr_2"}).json()
    assert [r["execution_id"] for r in filtered] == ["exec_b"]


def test_list_executions_respects_limit(client, sample_event):
    for i in range(3):
        client.post("/run-workflow", json={"execution_id": f"exec_{i}", "event": sample_event})
    assert len(client.get("/executions", params={"limit": 2}).json()) == 2


def test_list_executions_correlation_no_match_is_empty(client, sample_event):
    # FR-AU-22: the Admin UI's "no match" state depends on an empty list, not a 404.
    client.post("/run-workflow", json={"execution_id": "exec_a", "event": sample_event})
    assert client.get("/executions", params={"correlation_id": "does-not-exist"}).json() == []


def test_list_executions_orders_newest_first(client, sample_event, course_event):
    # FR-AU-16: ordered by updated_at desc, execution_id desc — exec_b ran last.
    client.post("/run-workflow", json={"execution_id": "exec_a", "event": sample_event})
    client.post("/run-workflow", json={"execution_id": "exec_b", "event": course_event})
    rows = client.get("/executions").json()
    assert [r["execution_id"] for r in rows] == ["exec_b", "exec_a"]


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
    ENV_FILE.write_text(
        "ORCHESTRATOR_DB_PATH=:memory:\nLEARNCARD_DEMO_RECIPIENT_PROFILE_ID=@demo\n"
    )
    try:
        s = Settings()
        assert s.db_path == ":memory:"
        assert s.demo_recipient_profile_id == "@demo"  # validation_alias, LEARNCARD_-prefixed
    finally:
        if original is None:
            ENV_FILE.unlink()
        else:
            ENV_FILE.write_text(original)
