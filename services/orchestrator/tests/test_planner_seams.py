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


class _StubWA:
    """Configured Workflow Actions client that succeeds — exercises the wrapper's
    pass-through return path (which otherwise only runs against a live service)."""

    def __init__(self, *, gate: GateDecision, plan: DeliveryPhasePlan) -> None:
        self._gate = gate
        self._plan = plan
        self.gate_calls = 0
        self.plan_calls = 0

    def pre_target_gate(self, *a: Any, **k: Any) -> GateDecision:
        self.gate_calls += 1
        return self._gate

    def delivery_phase_plan(self, *a: Any, **k: Any) -> DeliveryPhasePlan:
        self.plan_calls += 1
        return self._plan


class _StubDT:
    """Configured Delivery Targets client that succeeds (pass-through return path)."""

    def __init__(self, targets: list[str]) -> None:
        self._targets = targets
        self.calls = 0

    def select_targets(self, *a: Any, **k: Any) -> list[str]:
        self.calls += 1
        return self._targets


# --- best-effort fallback (the whole point of the seam) ---


def test_gate_uses_deterministic_when_unconfigured() -> None:
    gate, source = _resolve_gate(None, "skill_mastered", {}, {}, _CTX)
    assert gate.decision == "continue"
    assert source == "deterministic_fallback"


def test_gate_falls_back_when_service_raises() -> None:
    # A failing Workflow Actions gate must NOT fail the workflow — deterministic fallback.
    gate, source = _resolve_gate(_RaisingWA(), "skill_mastered", {}, {}, _CTX)
    assert gate.decision == "continue"
    # The deterministic gate reports no LLM confidence (None), not a fake 1.0.
    assert gate.confidence is None
    # Provenance is explicit — confidence alone can't distinguish a fallback.
    assert source == "deterministic_fallback"


def test_targets_fall_back_when_service_raises() -> None:
    targets, source = _resolve_targets(_RaisingDT(), "skill_mastered", "mock_lms", {}, _CTX)
    assert targets == planner.select_delivery_targets()
    assert source == "deterministic_fallback"


def test_plan_falls_back_when_service_raises() -> None:
    plan, source = _resolve_plan(
        _RaisingWA(), "skill_mastered", "mock_lms", ["learncard_issuer"], {}, {},
        "2026-01-01T00:00:00Z", _CTX,
    )
    assert isinstance(plan, DeliveryPhasePlan)
    assert plan.plan_id  # the deterministic plan
    assert plan.confidence is None  # deterministic plan carries no LLM confidence
    assert source == "deterministic_fallback"


_TARGETS = ["learncard_issuer", "learncard_wallet"]

# --- configured-and-succeeds: the wrapper returns the service's result ---
# (these exercise the pass-through return line that otherwise only runs in production)


def test_gate_uses_service_result_when_configured_and_succeeds() -> None:
    decision = GateDecision(decision="terminate", confidence=0.7, rationale="failing grade")
    plan = planner.delivery_phase_plan("skill_mastered", _TARGETS, "2026-01-01T00:00:00Z")
    wa = _StubWA(gate=decision, plan=plan)
    result, source = _resolve_gate(wa, "skill_mastered", {}, {}, _CTX)
    assert wa.gate_calls == 1
    assert result is decision  # service result, not the deterministic gate
    assert source == "llm"


def test_targets_use_service_result_when_configured_and_succeeds() -> None:
    dt = _StubDT(["smart_resume"])
    result, source = _resolve_targets(dt, "course_completed", "mock_lms", {}, _CTX)
    assert dt.calls == 1
    assert result == ["smart_resume"]  # service result, not the deterministic default
    assert source == "llm"


def test_plan_uses_service_result_when_configured_and_succeeds() -> None:
    plan = planner.delivery_phase_plan("skill_mastered", _TARGETS, "2026-01-01T00:00:00Z")
    gate = GateDecision(decision="continue", confidence=1.0, rationale="")
    wa = _StubWA(gate=gate, plan=plan)
    result, source = _resolve_plan(
        wa, "skill_mastered", "mock_lms", _TARGETS, {}, {}, "2026-01-01T00:00:00Z", _CTX,
    )
    assert wa.plan_calls == 1
    assert result is plan  # service result, not deterministic regeneration
    assert source == "llm"


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
    assert gate.confidence == 0.9  # a supplied confidence is preserved


def test_http_gate_continue_passes_through() -> None:
    client = HttpWorkflowActionsClient(
        "http://x",
        client=_FakeHttp(  # type: ignore[arg-type]
            {"status": "succeeded", "decision": "continue", "rationale": "ok"}
        ),
    )
    gate = client.pre_target_gate("skill_mastered", {}, {}, _CTX)
    assert gate.decision == "continue"
    # An omitted confidence stays None (not a fake 1.0) so it's distinguishable from a
    # genuine full-confidence decision (Phil, #79 review).
    assert gate.confidence is None


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
