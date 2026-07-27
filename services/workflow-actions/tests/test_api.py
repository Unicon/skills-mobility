from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from workflow_actions.api import create_app
from workflow_actions.config import Settings
from workflow_actions.plan_store import PlanStore
from workflow_actions.replay_adapter import ReplayAdapter
from workflow_actions.service import WorkflowActionsService

from .conftest import SKILL_MASTERED_GATE_BODY, SKILL_MASTERED_PLAN_BODY

_GATE_SEAM_KEYS = {"status", "decision", "confidence", "rationale", "llm_invocation_log_ref"}
_PLAN_SEAM_KEYS = {
    "status",
    "plan",
    "plan_ref",
    "confidence",
    "rationale",
    "llm_invocation_log_ref",
}


def _client(tmp_path: Path) -> TestClient:
    service = WorkflowActionsService(
        settings=Settings(mode="replay"),
        plan_store=PlanStore(tmp_path / "artifacts"),
        adapter=ReplayAdapter(),
    )
    return TestClient(create_app(service))


def test_post_gate_returns_seam_envelope(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/pre-target-gate", json=SKILL_MASTERED_GATE_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _GATE_SEAM_KEYS
    assert body["status"] == "succeeded"
    assert body["decision"] == "continue"


def test_post_plan_returns_seam_envelope(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/delivery-phase-plan", json=SKILL_MASTERED_PLAN_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _PLAN_SEAM_KEYS
    assert body["status"] == "succeeded"
    assert body["plan"] is not None
    assert body["plan_ref"] is not None


def test_post_gate_contract_violation_is_422(tmp_path: Path) -> None:
    bad: dict[str, Any] = {"execution_id": "exec_1"}
    resp = _client(tmp_path).post("/pre-target-gate", json=bad)
    assert resp.status_code == 422


def test_post_plan_contract_violation_is_422(tmp_path: Path) -> None:
    bad: dict[str, Any] = {"execution_id": "exec_1"}
    resp = _client(tmp_path).post("/delivery-phase-plan", json=bad)
    assert resp.status_code == 422


def test_healthz_returns_ok(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_unknown_mode_rejected_at_settings_construction() -> None:
    import pydantic
    import pytest

    # mode is a Literal["replay", "bedrock"] — typos fail at config load, before
    # build_service ever runs.
    with pytest.raises(pydantic.ValidationError):
        Settings(mode="unknown_mode")  # type: ignore[arg-type]
