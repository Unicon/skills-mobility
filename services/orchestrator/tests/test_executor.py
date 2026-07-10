"""Executor path: step order + persistence, input-binding resolution (DID and
profile threaded through), and the issuer-failure short-circuit."""

from __future__ import annotations

from typing import Any

from orchestrator import planner
from orchestrator.actions import ActionDeps
from orchestrator.clients import (
    EnvelopeContext,
    StubContextBuilder,
    StubDeliveryRouter,
    StubFieldMapping,
    StubProfileResolver,
)
from orchestrator.executor import execute_plan
from orchestrator.store import ExecutionStore

_ENVELOPE = EnvelopeContext(
    workflow_id="exec_1",
    execution_id="exec_1",
    correlation_id="corr_1",
    delivery_config_ref="phase1-learncard-default",
)


class SpyProfileResolver:
    def __init__(self) -> None:
        self.seen: list[str] = []
        self._inner = StubProfileResolver()

    def resolve(
        self, learner_id_type: str, learner_id_value: str, ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        self.seen.append(learner_id_value)
        return self._inner.resolve(learner_id_type, learner_id_value, ctx, step_id)


class SpyDeliveryRouter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._inner = StubDeliveryRouter()

    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        self.calls.append((action, payload))
        return self._inner.dispatch(action, payload, ctx, step_id)


def _ctx(event: dict[str, Any]) -> dict[str, Any]:
    bundle = StubContextBuilder().build_context("exec_1", event)
    return {
        "event": event,
        "bundle": bundle,
        "issuer_id": "did:web:issuer.example",
        "delivery_config_ref": "phase1-learncard-default",
        "learner_id_value": event["metadata"]["user_id"],
    }


def _plan():
    targets = planner.select_delivery_targets()
    return planner.delivery_phase_plan("skill_mastered", targets, "2026-06-24T00:00:00Z")


def test_executes_steps_in_order_and_threads_data(sample_event):
    store = ExecutionStore(":memory:")
    store.create_execution("exec_1", "evt_1", "corr_1", "skill_mastered")
    profile, router = SpyProfileResolver(), SpyDeliveryRouter()
    deps = ActionDeps(
        profile_resolver=profile,
        delivery_router=router,
        field_mapping=StubFieldMapping(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )

    status, result = execute_plan(_plan(), _ctx(sample_event), deps, store, "exec_1")

    assert status == "completed"
    # The workflow-path binding fed the learner id into profile resolution.
    assert profile.seen == ["WU1125875"]
    # Issue precedes wallet delivery.
    assert [a for a, _ in router.calls] == ["issue_learncard_badge", "deliver_to_learncard_wallet"]
    # Step bindings threaded the resolved DID into the issuer payload...
    unsigned = router.calls[0][1]["unsigned_vc"]
    assert unsigned["credentialSubject"]["id"].startswith("did:web:")
    # ...and the signed credential + resolved profile into wallet delivery.
    wallet = router.calls[1][1]
    assert "proof" in wallet["signed_credential"]
    assert wallet["recipient_profile_id"].startswith("@")
    assert result["recipient_profile_id"].startswith("@")

    # All eight steps persisted as succeeded, in order.
    meta = store.get_execution_metadata("exec_1")
    assert meta is not None
    assert [s.step_id for s in meta.steps] == list(range(1, 9))
    assert all(s.status == "succeeded" for s in meta.steps)

    # Field Mapping seam (#27): the mapping steps emit exactly the §10 response
    # envelope. transformation_type / synthesis_allowed are request literals from
    # the plan, not response fields; requires_synthesis is derived (false here —
    # the stub maps every field directly, so no placeholders/synthesis request).
    by_action = {s.action_id: s.output for s in meta.steps}
    issuer_map = by_action["generate_issuer_payload_mapping"]
    wallet_map = by_action["generate_wallet_payload_mapping"]
    assert issuer_map.keys() == {
        "status",
        "mapping_artifact_ref",
        "synthesis_request_ref",
        "requires_synthesis",
        "llm_invocation_log_ref",
    }
    assert "transformation_type" not in issuer_map
    assert issuer_map["requires_synthesis"] is False
    assert wallet_map["requires_synthesis"] is False
    # Field Synthesis seam: flat synthesized-values map (empty in Phase 1).
    assert by_action["generate_issuer_payload_synthesis"] == {"synthesized": {}}


class _FailingIssuer:
    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        if action == "issue_learncard_badge":
            return {"status": "failed", "action": action, "error": {"message": "issuer down"}}
        return {"status": "succeeded", "action": action, "result": {}}


def test_issuer_failure_short_circuits_before_wallet(sample_event):
    store = ExecutionStore(":memory:")
    store.create_execution("exec_2", "evt_1", "corr_1", "skill_mastered")
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=_FailingIssuer(),
        field_mapping=StubFieldMapping(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )

    status, _ = execute_plan(_plan(), _ctx(sample_event), deps, store, "exec_2")

    assert status == "failed"
    meta = store.get_execution_metadata("exec_2")
    assert meta is not None
    action_ids = [s.action_id for s in meta.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" not in action_ids
    assert meta.steps[-1].status == "failed"
