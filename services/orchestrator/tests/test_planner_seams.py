"""LLM Decision Service planner seams: best-effort wiring + HTTP client parsing."""

from typing import Any

import pytest
from orchestrator import planner
from orchestrator.clients import (
    EnvelopeContext,
    HttpDeliveryTargetsClient,
    HttpWorkflowActionsClient,
)
from orchestrator.engine import _resolve_gate, _resolve_plan, _resolve_targets
from orchestrator.schemas import DeliveryPhasePlan, GateDecision

_CTX = EnvelopeContext(
    workflow_id="e1", execution_id="e1", correlation_id="c1", delivery_config_ref="cfg"
)


class _FakeResp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # noqa: D401
        pass

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHttp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last: tuple[str, dict[str, Any]] | None = None

    def post(self, path: str, json: dict[str, Any]) -> _FakeResp:
        self.last = (path, json)
        return _FakeResp(self._payload)


class _RaisingWA:
    def pre_target_gate(self, *a: Any, **k: Any) -> GateDecision:
        raise RuntimeError("service down")

    def delivery_phase_plan(self, *a: Any, **k: Any) -> DeliveryPhasePlan:
        raise RuntimeError("service down")


class _RaisingDT:
    def select_targets(self, *a: Any, **k: Any) -> list[str]:
        raise RuntimeError("service down")


# --- best-effort fallback (the whole point of the seam) ---


def test_gate_uses_deterministic_when_unconfigured() -> None:
    gate = _resolve_gate(None, "skill_mastered", {}, {}, _CTX)
    assert gate.decision == "continue_to_delivery_targets"


def test_gate_falls_back_when_service_raises() -> None:
    # A failing Workflow Actions gate must NOT fail the workflow — deterministic fallback.
    assert _resolve_gate(_RaisingWA(), "skill_mastered", {}, {}, _CTX).decision == (
        "continue_to_delivery_targets"
    )


def test_targets_fall_back_when_service_raises() -> None:
    assert _resolve_targets(_RaisingDT(), "skill_mastered", "mock_lms", {}, _CTX) == (
        planner.select_delivery_targets()
    )


def test_plan_falls_back_when_service_raises() -> None:
    plan = _resolve_plan(
        _RaisingWA(), "skill_mastered", "mock_lms", ["learncard_issuer"], {}, {},
        "2026-01-01T00:00:00Z", _CTX,
    )
    assert isinstance(plan, DeliveryPhasePlan)
    assert plan.plan_id  # the deterministic plan


# --- HTTP client parsing / decision normalization ---


def test_http_gate_normalizes_terminate_reason() -> None:
    client = HttpWorkflowActionsClient(
        "http://x",
        client=_FakeHttp(  # type: ignore[arg-type]
            {"status": "succeeded", "decision": "terminate_failing_grade", "confidence": 0.9,
             "rationale": "below threshold"}
        ),
    )
    gate = client.pre_target_gate("skill_mastered", {}, {}, _CTX)
    assert gate.decision == "terminate"  # normalized to the orchestrator's Literal
    assert "terminate_failing_grade" in gate.rationale  # specific reason preserved


def test_http_gate_continue_passes_through() -> None:
    client = HttpWorkflowActionsClient(
        "http://x",
        client=_FakeHttp(  # type: ignore[arg-type]
            {"status": "succeeded", "decision": "continue_to_delivery_targets", "rationale": "ok"}
        ),
    )
    assert client.pre_target_gate("skill_mastered", {}, {}, _CTX).decision == (
        "continue_to_delivery_targets"
    )


def test_http_client_failed_status_raises() -> None:
    dt = HttpDeliveryTargetsClient("http://x", client=_FakeHttp({"status": "failed"}))  # type: ignore[arg-type]
    with pytest.raises(RuntimeError):
        dt.select_targets("skill_mastered", "mock_lms", {}, _CTX)


def test_http_delivery_targets_returns_selected() -> None:
    dt = HttpDeliveryTargetsClient(
        "http://x",
        client=_FakeHttp(  # type: ignore[arg-type]
            {"status": "succeeded", "selected_targets": ["learncard_issuer", "learncard_wallet"]}
        ),
    )
    assert dt.select_targets("skill_mastered", "mock_lms", {}, _CTX) == [
        "learncard_issuer",
        "learncard_wallet",
    ]
