"""Direct unit tests for the orchestration engine: pre-target gate branching,
the context-builder failure path, and reusable delivery-phase plan lookup
(FR-OR-28 — both sides of the toggle)."""

from __future__ import annotations

import logging
from typing import Any

from orchestrator import engine, planner
from orchestrator.clients import (
    StubContextBuilder,
    StubDeliveryRouter,
    StubFieldMapping,
    StubFieldSynthesis,
    StubProfileResolver,
)
from orchestrator.schemas import (
    DeliveryPhasePlan,
    GateDecision,
    InputBinding,
    PlanApplicability,
    PlanGenerator,
    PlanStep,
    WorkflowStartRequest,
)
from orchestrator.store import ExecutionStore


def _run(event, *, store, reusable=False, execution_id="e1", context_builder=None):
    return engine.run_workflow(
        WorkflowStartRequest(execution_id=execution_id, event=event),
        store=store,
        context_builder=context_builder or StubContextBuilder(),
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        delivery_config_ref="cfg",
        recipient_profile_id="smi-demo-learner",
        reusable_plan_lookup=reusable,
    )


class _SpyResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._inner = StubProfileResolver()

    def resolve(
        self, learner_id_type: str, learner_id_value: str, ctx: Any, step_id: str
    ) -> dict[str, Any]:
        self.calls.append((learner_id_type, learner_id_value))
        return self._inner.resolve(learner_id_type, learner_id_value, ctx, step_id)


def test_resolves_fixed_demo_recipient_by_profile_id(sample_event):
    # ADR-0020: the POC resolves the fixed demo wallet by handle, never the event's
    # learner id (WU1125875) nor an email (which LearnCard Search can't match).
    resolver = _SpyResolver()
    engine.run_workflow(
        WorkflowStartRequest(execution_id="e1", event=sample_event),
        store=ExecutionStore(":memory:"),
        context_builder=StubContextBuilder(),
        profile_resolver=resolver,
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        delivery_config_ref="cfg",
        recipient_profile_id="smi-demo-learner",
    )
    assert resolver.calls == [("profile_id", "smi-demo-learner")]


def test_gate_continue_runs_full_plan(sample_event):
    meta = _run(sample_event, store=ExecutionStore(":memory:"))
    assert meta.status == "completed"
    assert meta.decisions[0].kind == "gate"
    assert meta.decisions[0].outcome == "continue"
    assert meta.plan_id == "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
    assert len(meta.steps) == 11


def test_continue_path_records_all_three_planner_decisions(sample_event):
    # Delivery Targets and Workflow Actions are unconfigured in tests, so both
    # fall back to the deterministic stubs (best-effort seams, #79) — the
    # decisions[] trail should still carry all three in order.
    meta = _run(sample_event, store=ExecutionStore(":memory:"))
    assert [d.kind for d in meta.decisions] == ["gate", "delivery_targets", "workflow_actions_plan"]
    targets_decision, plan_decision = meta.decisions[1], meta.decisions[2]
    assert targets_decision.outcome == "learncard_issuer, learncard_wallet"
    assert targets_decision.confidence is None
    assert plan_decision.outcome == "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
    assert plan_decision.confidence is None


class _FakeWorkflowActions:
    """A configured Workflow Actions client that succeeds, so decisions[] should
    carry ITS confidence/rationale rather than the deterministic fallback's."""

    def pre_target_gate(self, event_type, event, context_bundle, ctx):
        return GateDecision(
            decision="continue", confidence=0.42, rationale="real gate call"
        )

    def delivery_phase_plan(self, event_type, source_system, targets, event, bundle, ctx):
        return planner.delivery_phase_plan(event_type, targets, "2026-01-01T00:00:00Z").model_copy(
            update={"confidence": 0.77, "rationale": "real plan call"}
        )


def test_configured_workflow_actions_decisions_reflect_the_real_call(sample_event):
    meta = engine.run_workflow(
        WorkflowStartRequest(execution_id="e1", event=sample_event),
        store=ExecutionStore(":memory:"),
        context_builder=StubContextBuilder(),
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        delivery_config_ref="cfg",
        recipient_profile_id="smi-demo-learner",
        workflow_actions=_FakeWorkflowActions(),
    )
    gate_decision, _, plan_decision = meta.decisions
    assert gate_decision.confidence == 0.42
    assert gate_decision.rationale == "real gate call"
    assert plan_decision.confidence == 0.77
    assert plan_decision.rationale == "real plan call"


def test_llm_backed_decisions_are_labeled_llm(sample_event):
    """Provenance (ADR-0022): decisions from configured, succeeding seams carry
    decision_source="llm", and the accepted (re-bound) plan is labeled on both the
    decision record and the plan artifact."""
    meta = engine.run_workflow(
        WorkflowStartRequest(execution_id="e1", event=sample_event),
        store=ExecutionStore(":memory:"),
        context_builder=StubContextBuilder(),
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        delivery_config_ref="cfg",
        recipient_profile_id="smi-demo-learner",
        workflow_actions=_FakeWorkflowActions(),
    )
    gate_decision, targets_decision, plan_decision = meta.decisions
    assert gate_decision.decision_source == "llm"
    # Delivery Targets is unconfigured here -> its stub fallback stays labeled.
    assert targets_decision.decision_source == "deterministic_fallback"
    assert plan_decision.decision_source == "llm"


def test_unbindable_llm_plan_is_labeled_deterministic_fallback(sample_event):
    """When re-binding rejects the LLM proposal, the executed plan's decision
    record says deterministic_fallback — indistinguishable no more."""

    class _GarbagePlanWA(_FakeWorkflowActions):
        def delivery_phase_plan(self, event_type, source_system, targets, event, bundle, ctx):
            plan = planner.delivery_phase_plan(event_type, targets, "2026-01-01T00:00:00Z")
            garbage = plan.steps[0].model_copy(update={"action_id": "not_a_real_action"})
            return plan.model_copy(update={"steps": [garbage], "rationale": "garbage"})

    meta = engine.run_workflow(
        WorkflowStartRequest(execution_id="e1", event=sample_event),
        store=ExecutionStore(":memory:"),
        context_builder=StubContextBuilder(),
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        delivery_config_ref="cfg",
        recipient_profile_id="smi-demo-learner",
        workflow_actions=_GarbagePlanWA(),
    )
    plan_decision = meta.decisions[2]
    assert plan_decision.kind == "workflow_actions_plan"
    assert plan_decision.decision_source == "deterministic_fallback"
    assert meta.status == "completed"  # the fallback plan still executes


def test_engine_logs_key_transitions(sample_event, caplog):
    # The audit-traceability contract wants the run's key transitions visible.
    with caplog.at_level(logging.INFO, logger="orchestrator"):
        _run(sample_event, store=ExecutionStore(":memory:"))
    log = " ".join(caplog.messages)
    assert "gate decision" in log
    assert "delivery-phase plan generated" in log
    assert "workflow completed" in log
    assert "step 1" in log  # executor logs each step


def test_gate_terminate_skips_delivery():
    # An unsupported event type → the pre-target gate terminates before delivery.
    event = {"metadata": {"event_name": "badge_awarded", "user_id": "U1"}, "body": {}}
    meta = _run(event, store=ExecutionStore(":memory:"))
    assert meta.status == "completed"
    assert meta.decisions[0].kind == "gate"
    assert meta.decisions[0].outcome == "terminate"
    assert meta.plan_id is None
    assert meta.steps == []
    assert meta.result["outcome"] == "terminated_before_delivery"


class _FailingContextBuilder:
    def build_context(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return {"context_builder_error": {"code": "boom"}}


def test_context_builder_failure_marks_failed(sample_event):
    meta = _run(
        sample_event, store=ExecutionStore(":memory:"), context_builder=_FailingContextBuilder()
    )
    assert meta.status == "failed"
    assert meta.steps == []


def _stored_plan(event_type: str, targets: list[str]) -> DeliveryPhasePlan:
    """A distinctive 1-step plan so a test can tell whether lookup used it."""
    return DeliveryPhasePlan(
        plan_id="STORED.v1",
        generator=PlanGenerator(service_version="test"),
        applicability=PlanApplicability(event_type=event_type, selected_targets=targets),
        steps=[
            PlanStep(
                step_id=1,
                action_id="resolve_learncard_profile",
                inputs={
                    "learner_id_value": InputBinding(source="workflow", path="learner_id_value"),
                },
                produces="resolved_profile",
            )
        ],
    )


def _seed_stored_plan(store: ExecutionStore) -> None:
    targets = planner.select_delivery_targets()
    key = planner.applicability_key("skill_mastered", targets)
    store.save_plan(_stored_plan("skill_mastered", targets), key)


def test_plan_lookup_disabled_ignores_stored_plan(sample_event):
    store = ExecutionStore(":memory:")
    _seed_stored_plan(store)
    meta = _run(sample_event, store=store, reusable=False)
    # Lookup off → the stored plan is ignored; a fresh Phase-1 plan is generated.
    assert meta.plan_id == "phase1-skill_mastered.learncard_issuer.learncard_wallet.v1"
    assert len(meta.steps) == 11


def test_plan_lookup_enabled_uses_stored_plan(sample_event):
    store = ExecutionStore(":memory:")
    _seed_stored_plan(store)
    meta = _run(sample_event, store=store, reusable=True)
    # Lookup on → the stored plan is retrieved and run (its single custom step).
    assert meta.plan_id == "STORED.v1"
    assert [s.action_id for s in meta.steps] == ["resolve_learncard_profile"]
