"""Tests for planner.rebind_plan — re-binding LLM action sequences to executor
bindings (ADR-0022). Each test builds a DeliveryPhasePlan with deliberately wrong
or empty inputs to prove that re-binding replaces them."""

from __future__ import annotations

from orchestrator import planner
from orchestrator.actions import ActionDeps
from orchestrator.clients import (
    EnvelopeContext,
    StubDeliveryRouter,
    StubFieldMapping,
    StubFieldSynthesis,
    StubProfileResolver,
)
from orchestrator.executor import execute_plan
from orchestrator.schemas import (
    DeliveryPhasePlan,
    PlanApplicability,
    PlanGenerator,
    PlanStep,
)
from orchestrator.store import ExecutionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LC_TARGETS = ["learncard_issuer", "learncard_wallet"]
_SR_TARGETS = ["smart_resume"]


def _llm_plan(action_ids: list[str]) -> DeliveryPhasePlan:
    """Minimal LLM-shaped plan: correct action sequence, empty inputs everywhere.
    Re-binding must replace the inputs with correct executor bindings."""
    return DeliveryPhasePlan(
        plan_id="llm-test.v1",
        generator=PlanGenerator(service_version="test-llm"),
        applicability=PlanApplicability(
            event_type="skill_mastered", selected_targets=_LC_TARGETS
        ),
        steps=[
            PlanStep(step_id=i, action_id=action_id, inputs={}, produces=None)
            for i, action_id in enumerate(action_ids, start=1)
        ],
    )


def _action_deps() -> tuple[ActionDeps, EnvelopeContext]:
    envelope = EnvelopeContext(
        workflow_id="test", execution_id="test", correlation_id="c1", delivery_config_ref="cfg"
    )
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=envelope,
    )
    return deps, envelope


_LC_ACTIONS = [
    "resolve_learncard_profile",
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "execute_issuer_payload_translation",
    "issue_learncard_badge",
    "generate_wallet_payload_mapping",
    "execute_wallet_payload_translation",
    "deliver_to_learncard_wallet",
]

_SR_ACTIONS = [
    "resolve_learncard_profile",
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "execute_issuer_payload_translation",
    "deliver_to_smartresume",
]


# ---------------------------------------------------------------------------
# (a) Well-formed LLM plan with empty inputs re-binds and executes
# ---------------------------------------------------------------------------


def test_rebind_learncard_plan_fixes_step_bindings() -> None:
    """An LLM plan with correct action sequence but empty inputs re-binds to correct
    bindings: the execute_issuer_payload_translation step's resolved_profile input must
    point (source=step) at the resolve step's re-bound step_id."""
    llm_plan = _llm_plan(_LC_ACTIONS)
    rebound = planner.rebind_plan(llm_plan, "skill_mastered")

    assert rebound is not None

    # step_ids are reassigned 1-N in order
    assert [s.step_id for s in rebound.steps] == list(range(1, len(_LC_ACTIONS) + 1))

    # execute_issuer_payload_translation is step 4; its resolved_profile should point at
    # step 1 (resolve_learncard_profile, which produces "resolved_profile")
    translation_step = next(
        s for s in rebound.steps if s.action_id == "execute_issuer_payload_translation"
    )
    resolved_profile_binding = translation_step.inputs["resolved_profile"]
    assert resolved_profile_binding.source == "step"
    resolve_step_id = next(
        s.step_id for s in rebound.steps if s.action_id == "resolve_learncard_profile"
    )
    assert resolved_profile_binding.step_id == resolve_step_id


def test_rebind_learncard_plan_executes_successfully() -> None:
    """A re-bound LLM plan (empty inputs replaced) executes to completion."""
    llm_plan = _llm_plan(_LC_ACTIONS)
    rebound = planner.rebind_plan(llm_plan, "skill_mastered")
    assert rebound is not None

    deps, envelope = _action_deps()
    store = ExecutionStore(":memory:")
    store.create_execution("test", "", "", "skill_mastered")

    workflow_ctx = {
        "event": {},
        "bundle": {"source_data": {}},
        "issuer_id": "did:web:issuer.example",
        "delivery_config_ref": "cfg",
        "learner_id_value": "smi-demo-learner",
    }
    status, _ = execute_plan(rebound, workflow_ctx, deps, store, "test")
    assert status == "completed"


# ---------------------------------------------------------------------------
# (b) Unmet dependency (translation before mapping) → None
# ---------------------------------------------------------------------------


def test_rebind_returns_none_when_dependency_unmet() -> None:
    """A plan that runs execute_issuer_payload_translation before
    resolve_learncard_profile (which produces the resolved_profile dependency)
    cannot be re-bound — rebind_plan must return None."""
    # Put translation first so resolved_profile hasn't been produced yet
    bad_order = [
        "execute_issuer_payload_translation",  # needs resolved_profile → not produced yet
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "issue_learncard_badge",
        "generate_wallet_payload_mapping",
        "execute_wallet_payload_translation",
        "deliver_to_learncard_wallet",
    ]
    llm_plan = _llm_plan(bad_order)
    assert planner.rebind_plan(llm_plan, "skill_mastered") is None


# ---------------------------------------------------------------------------
# (c) Unknown action_id → None
# ---------------------------------------------------------------------------


def test_rebind_returns_none_for_unknown_action() -> None:
    """A plan containing an action_id not in the deterministic planner's catalog
    cannot be re-bound."""
    llm_plan = _llm_plan(["resolve_learncard_profile", "invent_new_action"])
    assert planner.rebind_plan(llm_plan, "skill_mastered") is None


# ---------------------------------------------------------------------------
# (d) Idempotence: rebind(delivery_phase_plan(...)) yields same action_ids
# ---------------------------------------------------------------------------


def test_rebind_is_idempotent_on_deterministic_plan() -> None:
    """Applying rebind_plan to a plan already produced by delivery_phase_plan yields
    a plan with the same action_ids in the same order and resolvable bindings."""
    ref = planner.delivery_phase_plan("skill_mastered", _LC_TARGETS, "2026-01-01T00:00:00Z")
    rebound = planner.rebind_plan(ref, "skill_mastered")

    assert rebound is not None
    assert [s.action_id for s in rebound.steps] == [s.action_id for s in ref.steps]

    # All step-source bindings must reference existing step_ids in the rebound plan
    rebound_ids = {s.step_id for s in rebound.steps}
    for step in rebound.steps:
        for binding in step.inputs.values():
            if binding.source == "step":
                assert binding.step_id in rebound_ids, (
                    f"step {step.step_id} ({step.action_id}) references "
                    f"step_id={binding.step_id} which is not in the rebound plan"
                )


# ---------------------------------------------------------------------------
# (e) SmartResume LLM plan re-binds and executes
# ---------------------------------------------------------------------------


def test_rebind_smartresume_plan_executes_successfully() -> None:
    """A SmartResume-shaped LLM plan (resolve→mapping→synthesis→translation→deliver)
    with empty inputs re-binds and executes to completion."""
    llm_plan = DeliveryPhasePlan(
        plan_id="llm-smartresume.v1",
        generator=PlanGenerator(service_version="test-llm"),
        applicability=PlanApplicability(
            event_type="skill_mastered", selected_targets=_SR_TARGETS
        ),
        steps=[
            PlanStep(step_id=i, action_id=action_id, inputs={}, produces=None)
            for i, action_id in enumerate(_SR_ACTIONS, start=1)
        ],
    )

    rebound = planner.rebind_plan(llm_plan, "skill_mastered")
    assert rebound is not None

    # deliver_to_smartresume step must exist and have its issuer_payload bound to the
    # translation step's output
    deliver_step = next(
        s for s in rebound.steps if s.action_id == "deliver_to_smartresume"
    )
    assert deliver_step.inputs["issuer_payload"].source == "step"
    translation_step_id = next(
        s.step_id for s in rebound.steps if s.action_id == "execute_issuer_payload_translation"
    )
    assert deliver_step.inputs["issuer_payload"].step_id == translation_step_id

    deps, envelope = _action_deps()
    store = ExecutionStore(":memory:")
    store.create_execution("test-sr", "", "", "skill_mastered")

    workflow_ctx = {
        "event": {},
        "bundle": {"source_data": {}},
        "issuer_id": "did:web:issuer.example",
        "delivery_config_ref": "cfg",
        "learner_id_value": "smi-demo-learner",
    }
    status, _ = execute_plan(rebound, workflow_ctx, deps, store, "test-sr")
    assert status == "completed"
