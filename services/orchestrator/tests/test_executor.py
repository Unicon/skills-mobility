"""Executor path: step order + persistence, input-binding resolution (DID and
profile threaded through), and the issuer-failure short-circuit."""

from __future__ import annotations

from typing import Any

from orchestrator import planner
from orchestrator.actions import (
    ActionDeps,
    _deliver_to_smartresume,
    _execute_credential_template_translation,
    _execute_smartresume_payload_translation,
)
from orchestrator.clients import (
    EnvelopeContext,
    StubContextBuilder,
    StubDeliveryRouter,
    StubFieldMapping,
    StubFieldSynthesis,
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
        field_synthesis=StubFieldSynthesis(),
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
    # The stand-in VC must carry a top-level id — SmartResume delivery 400s
    # without one, and the mapped path is schema-guaranteed to include it.
    assert unsigned["id"].startswith("urn:poc:credential:")
    # ...and the signed credential + resolved profile into wallet delivery.
    wallet = router.calls[1][1]
    assert "proof" in wallet["signed_credential"]
    # Plain profileId — the wallet API path-interpolates it ("@" 404s live).
    assert not wallet["recipient_profile_id"].startswith("@")
    assert result["recipient_profile_id"] == wallet["recipient_profile_id"]
    # The summary reads the wallet delivery result (#139).
    assert result["delivery"] == {"delivery_state": "accepted"}

    # All eleven steps persisted as succeeded, in order.
    meta = store.get_execution_metadata("exec_1")
    assert meta is not None
    assert [s.step_id for s in meta.steps] == list(range(1, 12))
    assert all(s.status == "succeeded" for s in meta.steps)

    # Field Mapping seam (#27): the mapping steps emit exactly the §10 response
    # envelope. transformation_type / synthesis_allowed are request literals from
    # the plan, not response fields; requires_synthesis is derived (false here —
    # the stub maps every field directly, so no placeholders/synthesis request).
    by_action = {s.action_id: s.output for s in meta.steps}
    issuer_map = by_action["generate_issuer_payload_mapping"]
    wallet_map = by_action["generate_learncard_wallet_payload_mapping"]
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
        field_synthesis=StubFieldSynthesis(),
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


# --- SmartResume delivery branch ---


class SpySmartResumeRouter:
    """Spy + stub delivery router that captures deliver_to_smartresume calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._inner = StubDeliveryRouter()

    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        self.calls.append((action, payload))
        return self._inner.dispatch(action, payload, ctx, step_id)


def test_credential_template_translation_derives_achievement_from_outcome():
    """Unit test for the credential-template stand-in: name/description/criteria
    derive from the bundle's outcome data (ADR-0017 Phase 1)."""
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )
    inputs: dict[str, Any] = {
        "bundle": {
            "source_data": {
                "outcome": {
                    "display_name": "Demonstrate the sample competency",
                    "description": "Demonstrates mastery of the sample competency.",
                }
            }
        },
    }

    out = _execute_credential_template_translation(inputs, deps)

    template = out["credential_template"]
    assert template["name"] == "Demonstrate the sample competency"
    assert template["description"] == "Demonstrates mastery of the sample competency."
    assert template["criteria"] == {
        "narrative": "Demonstrates mastery of the sample competency."
    }


def test_credential_template_translation_falls_back_when_outcome_absent():
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )
    out = _execute_credential_template_translation({"bundle": {"source_data": {}}}, deps)

    template = out["credential_template"]
    assert template["name"] == "Credential"
    assert template["description"] == "Demonstrated mastery: Credential."
    assert template["criteria"] == {"narrative": "Awarded for Credential."}


def test_smartresume_translation_builds_payload_and_delivery_dispatches():
    """Unit test for the translation + delivery pair: the translation action builds
    the CredentialConnect payload from the issued credential; the delivery action
    dispatches it unchanged."""
    router = SpySmartResumeRouter()
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=router,
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )
    issued_credential = {
        "@context": ["https://www.w3.org/2018/credentials/v1"],
        "type": ["VerifiableCredential"],
    }
    inputs: dict[str, Any] = {
        "issued": {"result": {"issued_credential": issued_credential}},
        "resolved_profile": {"did": "did:web:example.com:users:alice", "profile_id": "@alice"},
        "bundle": {
            "source_data": {
                "learner_profile": {"email": "alice@example.com", "givenName": "Alice",
                                    "familyName": "Smith"},
            }
        },
    }

    payload = _execute_smartresume_payload_translation(inputs, deps)

    cred = payload["credentials"][0]
    assert cred["id"] == "urn:poc:credential:exec_1"  # stamped from envelope execution_id
    assert cred["type"] == issued_credential["type"]  # original OB3 fields preserved
    assert cred["@context"] == issued_credential["@context"]
    assert payload["recipient"]["id"] == "did:web:example.com:users:alice"
    assert payload["recipient"]["email"] == "alice@example.com"
    assert payload["recipient"]["givenName"] == "Alice"
    assert payload["recipient"]["familyName"] == "Smith"

    result = _deliver_to_smartresume({"smartresume_payload": payload}, deps)
    assert result["status"] == "succeeded"
    assert result["external_reference_id"] == "stub-smartresume"
    assert "redirect_url" in result["result"]
    assert len(router.calls) == 1
    action, dispatched = router.calls[0]
    assert action == "deliver_to_smartresume"
    assert dispatched == payload


def test_smartresume_translation_falls_back_to_email_when_no_did():
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=SpySmartResumeRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )
    inputs: dict[str, Any] = {
        "issued": {"result": {"issued_credential": {}}},
        "resolved_profile": {"profile_id": "@bob"},  # no DID
        "bundle": {"source_data": {"learner_profile": {"email": "bob@example.com"}}},
    }

    payload = _execute_smartresume_payload_translation(inputs, deps)

    assert payload["recipient"]["id"] == "mailto:bob@example.com"
    # No givenName / familyName when absent from learner_profile
    assert "givenName" not in payload["recipient"]
    assert "familyName" not in payload["recipient"]


def test_smartresume_plan_executes_end_to_end(sample_event):
    """Execute the smart_resume plan; issuance runs first (only issuer), then
    deliver_to_smartresume — and no wallet steps."""
    store = ExecutionStore(":memory:")
    store.create_execution("exec_sr", "evt_1", "corr_1", "skill_mastered")
    router = SpySmartResumeRouter()
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=router,
        field_mapping=StubFieldMapping(),
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENVELOPE,
    )
    plan = planner.delivery_phase_plan("skill_mastered", ["smart_resume"], "2026-06-24T00:00:00Z")

    status, result = execute_plan(plan, _ctx(sample_event), deps, store, "exec_sr")

    assert status == "completed"
    dispatched_actions = [a for a, _ in router.calls]
    assert dispatched_actions == ["issue_learncard_badge", "deliver_to_smartresume"]
    # The summary reads whichever delivery action the plan contained (#139) —
    # a smart_resume-only run must not report delivery: null.
    assert result["delivery"] == {
        "redirect_url": "https://mock.smartresume.example/createmyresume/stub"
    }
    # Issuance always runs; no wallet steps for a SmartResume selection.
    meta = store.get_execution_metadata("exec_sr")
    assert meta is not None
    action_ids = [s.action_id for s in meta.steps]
    assert "issue_learncard_badge" in action_ids
    assert "deliver_to_learncard_wallet" not in action_ids
    assert "deliver_to_smartresume" in action_ids
    assert all(s.status == "succeeded" for s in meta.steps)
