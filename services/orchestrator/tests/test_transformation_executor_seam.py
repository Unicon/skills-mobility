"""Transformation Executor seam (#98): best-effort wiring into the translation actions.

Tests:
(a) When the executor is configured and the mapping step returned JSONata, the
    executor is called and its result becomes the issuer/wallet payload.
(b) When the executor is None, or when it raises, the action falls back to the
    deterministic obv3 stand-in and the workflow still completes.
"""

from __future__ import annotations

from typing import Any

import pytest
from orchestrator.actions import (
    ActionDeps,
    _execute_issuer_payload_translation,
    _execute_wallet_payload_translation,
)
from orchestrator.clients import (
    EnvelopeContext,
    StubDeliveryRouter,
    StubFieldSynthesis,
    StubProfileResolver,
)

_ENV = EnvelopeContext(
    workflow_id="e1", execution_id="e1", correlation_id="c1", delivery_config_ref="cfg"
)

_PROFILE = {"did": "did:web:network.learncard.com:users:learner", "profile_id": "@learner"}

# A mapping envelope with inline JSONata (as produced by the field-mapping service
# when the `mapping` field is populated).
_MAPPING_WITH_JSONATA = {
    "status": "succeeded",
    "mapping_artifact_ref": "mapping:1",
    "synthesis_request_ref": None,
    "requires_synthesis": False,
    "llm_invocation_log_ref": "llmcall:1",
    "mapping": '{"unsigned_vc": {"type": "VerifiableCredential"}}',
}

# A mapping envelope that also carries an inline target_schema (ADR-#101).
_MAPPING_WITH_TARGET_SCHEMA = {
    **_MAPPING_WITH_JSONATA,
    "target_schema": {"type": "object", "required": ["unsigned_vc"]},
}

# A mapping envelope with no inline JSONata (legacy / stub response).
_MAPPING_NO_JSONATA = {
    "status": "succeeded",
    "mapping_artifact_ref": None,
    "synthesis_request_ref": None,
    "requires_synthesis": False,
    "llm_invocation_log_ref": None,
    "mapping": None,
}

_ISSUER_BASE = {
    "transformation_type": "issuer_payload",
    "delivery_target": "learncard_issuer",
    "bundle": {
        "source_data": {
            "outcome": {
                "title": "Sample Competency",
                "display_name": "Demonstrate the sample competency",
                "description": "A sample description.",
            },
            "learner_profile": {"email": "learner@example.com"},
        }
    },
    "issuer_id": "did:web:issuer.example",
    "resolved_profile": _PROFILE,
    "synthesis": {"synthesized": {}},
}

_WALLET_BASE = {
    "transformation_type": "wallet_payload",
    "delivery_target": "learncard_wallet",
    "issued": {
        "result": {
            "issued_credential": {
                "type": ["VerifiableCredential"],
                "proof": {"type": "stub", "jws": "stub-sig"},
            }
        }
    },
    "resolved_profile": _PROFILE,
}


class _SpyExecutor:
    """In-process fake that records calls and returns a canned result."""

    def __init__(
        self,
        result: dict[str, Any] | None = None,
        raise_exc: bool = False,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result
        self._raise = raise_exc

    def execute(
        self,
        transformation_type: str,
        delivery_target: str | None,
        mapping: str,
        source_payloads: dict[str, Any],
        synthesized: dict[str, Any],
        ctx: EnvelopeContext,
        target_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "transformation_type": transformation_type,
                "delivery_target": delivery_target,
                "mapping": mapping,
                "source_payloads": source_payloads,
                "synthesized": synthesized,
                "target_schema": target_schema,
            }
        )
        if self._raise:
            raise RuntimeError("executor unreachable")
        assert self._result is not None
        return self._result


def _deps(executor: Any = None) -> ActionDeps:
    return ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubDeliveryRouter(),  # not used in translation actions
        field_synthesis=StubFieldSynthesis(),
        issuer_id="did:web:issuer.example",
        envelope=_ENV,
        transformation_executor=executor,
    )


# --- Issuer payload translation ---


def test_issuer_executor_called_when_configured_with_jsonata() -> None:
    executor_result = {"type": "VerifiableCredential", "id": "urn:vc:1"}
    spy = _SpyExecutor(result=executor_result)
    inputs = {**_ISSUER_BASE, "mapping": _MAPPING_WITH_JSONATA}

    out = _execute_issuer_payload_translation(inputs, _deps(spy))

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["transformation_type"] == "issuer_payload"
    assert call["delivery_target"] == "learncard_issuer"
    assert call["mapping"] == _MAPPING_WITH_JSONATA["mapping"]
    assert call["synthesized"] == {}
    # The executor result is wrapped in unsigned_vc.
    assert out == {"unsigned_vc": executor_result}


def test_issuer_target_schema_threaded_to_executor() -> None:
    executor_result = {"type": "VerifiableCredential", "id": "urn:vc:1"}
    spy = _SpyExecutor(result=executor_result)
    inputs = {**_ISSUER_BASE, "mapping": _MAPPING_WITH_TARGET_SCHEMA}

    _execute_issuer_payload_translation(inputs, _deps(spy))

    assert len(spy.calls) == 1
    assert spy.calls[0]["target_schema"] == _MAPPING_WITH_TARGET_SCHEMA["target_schema"]


def test_issuer_executor_not_called_when_none() -> None:
    inputs = {**_ISSUER_BASE, "mapping": _MAPPING_WITH_JSONATA}
    out = _execute_issuer_payload_translation(inputs, _deps(None))

    # Falls back to obv3 stand-in; result has credentialSubject.id (the resolved DID).
    assert "unsigned_vc" in out
    assert out["unsigned_vc"]["credentialSubject"]["id"] == _PROFILE["did"]


def test_issuer_falls_back_when_no_jsonata_in_mapping_env() -> None:
    spy = _SpyExecutor(result={"type": "VerifiableCredential"})
    inputs = {**_ISSUER_BASE, "mapping": _MAPPING_NO_JSONATA}

    out = _execute_issuer_payload_translation(inputs, _deps(spy))

    # No JSONata → executor is skipped; obv3 stand-in is used.
    assert spy.calls == []
    assert "unsigned_vc" in out
    assert out["unsigned_vc"]["credentialSubject"]["id"] == _PROFILE["did"]


def test_issuer_falls_back_on_executor_exception() -> None:
    spy = _SpyExecutor(raise_exc=True)
    inputs = {**_ISSUER_BASE, "mapping": _MAPPING_WITH_JSONATA}

    out = _execute_issuer_payload_translation(inputs, _deps(spy))

    # Exception is non-fatal; obv3 stand-in still produces a valid payload.
    assert len(spy.calls) == 1
    assert "unsigned_vc" in out
    assert out["unsigned_vc"]["credentialSubject"]["id"] == _PROFILE["did"]


# --- Wallet payload translation ---


def test_wallet_executor_called_when_configured_with_jsonata() -> None:
    executor_result = {
        "signed_credential": {"proof": {}},
        "recipient_profile_id": "@learner",
    }
    spy = _SpyExecutor(result=executor_result)
    inputs = {**_WALLET_BASE, "mapping": _MAPPING_WITH_JSONATA}

    out = _execute_wallet_payload_translation(inputs, _deps(spy))

    assert len(spy.calls) == 1
    call = spy.calls[0]
    assert call["transformation_type"] == "wallet_payload"
    assert call["delivery_target"] == "learncard_wallet"
    assert call["mapping"] == _MAPPING_WITH_JSONATA["mapping"]
    # Executor result is returned directly (no wrapping).
    assert out == executor_result


def test_wallet_executor_not_called_when_none() -> None:
    inputs = {**_WALLET_BASE, "mapping": _MAPPING_WITH_JSONATA}
    out = _execute_wallet_payload_translation(inputs, _deps(None))

    # Falls back to obv3 prepare_wallet_input; result has signed_credential + profile.
    assert "signed_credential" in out
    assert out["recipient_profile_id"] == "@learner"


def test_wallet_falls_back_on_executor_exception() -> None:
    spy = _SpyExecutor(raise_exc=True)
    inputs = {**_WALLET_BASE, "mapping": _MAPPING_WITH_JSONATA}

    out = _execute_wallet_payload_translation(inputs, _deps(spy))

    assert len(spy.calls) == 1
    assert "signed_credential" in out
    assert out["recipient_profile_id"] == "@learner"


def test_wallet_falls_back_when_no_jsonata() -> None:
    spy = _SpyExecutor(result={"signed_credential": {}, "recipient_profile_id": "@learner"})
    inputs = {**_WALLET_BASE, "mapping": _MAPPING_NO_JSONATA}

    out = _execute_wallet_payload_translation(inputs, _deps(spy))

    assert spy.calls == []
    assert "signed_credential" in out


# --- HttpTransformationExecutorClient ---


def test_http_client_posts_and_returns_result() -> None:
    import json

    import httpx
    from orchestrator.clients import HttpTransformationExecutorClient

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "transformation_type": "issuer_payload",
                "result": {"type": "VerifiableCredential"},
                "error": None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://te")
    te = HttpTransformationExecutorClient("http://te", client=client)
    result = te.execute(
        transformation_type="issuer_payload",
        delivery_target="learncard_issuer",
        mapping='{"type": "VerifiableCredential"}',
        source_payloads={"outcome": {}},
        synthesized={},
        ctx=_ENV,
    )

    assert captured["path"] == "/execute"
    body = captured["body"]
    assert body["execution_id"] == "e1"
    assert body["transformation_type"] == "issuer_payload"
    assert body["delivery_target"] == "learncard_issuer"
    assert result == {"type": "VerifiableCredential"}


def test_http_client_raises_on_failed_status() -> None:
    import httpx
    from orchestrator.clients import HttpTransformationExecutorClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "failed",
                "transformation_type": "issuer_payload",
                "result": None,
                "error": {"error_type": "parse_error", "message": "bad jsonata"},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://te")
    te = HttpTransformationExecutorClient("http://te", client=client)

    with pytest.raises(RuntimeError, match="transformation-executor returned failed"):
        te.execute(
            transformation_type="issuer_payload",
            delivery_target=None,
            mapping='{"bad": }',
            source_payloads={},
            synthesized={},
            ctx=_ENV,
        )

# --- Plan-derived regression (review #102 item 1) ---


def test_wallet_executor_gets_issued_badge_when_driven_by_the_real_plan() -> None:
    """Regression: drive the PLANNER'S OWN plan through execute_plan (no hand-built
    inputs) and assert the wallet-phase executor call resolves issued_badge into
    source_payloads. The original bug: the wallet translation resolved payloads off
    the shared inputs dict, whose plan bindings carried no transformation_type, so
    it silently resolved issuer-shaped payloads and fell back undetected."""
    from orchestrator import planner
    from orchestrator.clients import StubContextBuilder, StubFieldMapping
    from orchestrator.executor import execute_plan
    from orchestrator.store import ExecutionStore

    class _PlanFieldMapping(StubFieldMapping):
        """Stub FM that returns inline JSONata + target_schema so the translation
        actions actually delegate to the (fake) Transformation Executor."""

        def map(self, request: dict[str, Any], ctx: Any, step_id: str) -> dict[str, Any]:
            if request.get("transformation_type") == "wallet_payload":
                return {
                    **_MAPPING_WITH_JSONATA,
                    "mapping": '{"signed_credential": source_payloads.issued_badge, '
                    '"recipient_profile_id": source_payloads.profile_resolution.'
                    'recipient_profile_id}',
                    "target_schema": {"type": "object", "required": ["signed_credential"]},
                }
            return dict(_MAPPING_WITH_JSONATA)

    executor = _SpyExecutor(result={"unsigned_vc": {"type": "VC"}})
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=_PlanFieldMapping(),
        issuer_id="did:web:issuer.example",
        envelope=_ENV,
        transformation_executor=executor,
    )
    store = ExecutionStore(":memory:")
    store.create_execution("exec_plan", "evt_1", "corr_1", "skill_mastered")
    plan = planner.delivery_phase_plan(
        "skill_mastered", planner.select_delivery_targets(), "2026-07-28T00:00:00Z"
    )
    bundle = StubContextBuilder().build_context("exec_plan", {"metadata": {}})
    workflow_ctx = {
        "event": {"metadata": {}},
        "bundle": bundle,
        "issuer_id": "did:web:issuer.example",
        "delivery_config_ref": "cfg",
        "learner_id_value": "smi-demo-learner",
    }

    status, _ = execute_plan(plan, workflow_ctx, deps, store, "exec_plan")
    assert status == "completed"

    wallet_calls = [
        c for c in executor.calls if c["transformation_type"] == "wallet_payload"
    ]
    assert wallet_calls, "wallet translation never reached the executor"
    payloads = wallet_calls[0]["source_payloads"]
    # The issued badge must be resolvable — this is exactly what went missing.
    assert "issued_badge" in payloads and payloads["issued_badge"], payloads

def test_degraded_fallback_is_persisted_but_not_delivered() -> None:
    """Review #102 item 2: when a best-effort seam falls back, the stored step
    output carries the _degraded marker (audit-visible), while the payload
    dispatched downstream does not."""
    from orchestrator import planner
    from orchestrator.clients import StubContextBuilder
    from orchestrator.executor import execute_plan
    from orchestrator.store import ExecutionStore

    class _JsonataFieldMapping:
        def map(self, request: dict[str, Any], ctx: Any, step_id: str) -> dict[str, Any]:
            return dict(_MAPPING_WITH_JSONATA)

    class _RecordingRouter(StubDeliveryRouter):
        def __init__(self) -> None:
            self.payloads: list[tuple[str, dict[str, Any]]] = []

        def dispatch(self, action: str, payload: dict[str, Any], ctx: Any, step_id: str):
            self.payloads.append((action, payload))
            return super().dispatch(action, payload, ctx, step_id)

    router = _RecordingRouter()
    deps = ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=router,
        field_mapping=_JsonataFieldMapping(),
        issuer_id="did:web:issuer.example",
        envelope=_ENV,
        transformation_executor=_SpyExecutor(raise_exc=True),  # every TE call fails
    )
    store = ExecutionStore(":memory:")
    store.create_execution("exec_deg", "evt_1", "corr_1", "skill_mastered")
    plan = planner.delivery_phase_plan(
        "skill_mastered", planner.select_delivery_targets(), "2026-07-28T00:00:00Z"
    )
    workflow_ctx = {
        "event": {"metadata": {}},
        "bundle": StubContextBuilder().build_context("exec_deg", {"metadata": {}}),
        "issuer_id": "did:web:issuer.example",
        "delivery_config_ref": "cfg",
        "learner_id_value": "smi-demo-learner",
    }

    status, _ = execute_plan(plan, workflow_ctx, deps, store, "exec_deg")
    assert status == "completed"  # best-effort: fallbacks keep the workflow green

    meta = store.get_execution_metadata("exec_deg")
    assert meta is not None
    degraded_steps = [s for s in meta.steps if (s.output or {}).get("_degraded")]
    # Both translation steps fell back — and the record says so.
    assert {s.action_id for s in degraded_steps} >= {
        "execute_issuer_payload_translation",
        "execute_wallet_payload_translation",
    }
    # The dispatched wallet payload carries no bookkeeping key.
    wallet_dispatches = [p for a, p in router.payloads if a == "deliver_to_learncard_wallet"]
    assert wallet_dispatches and "_degraded" not in wallet_dispatches[0]

