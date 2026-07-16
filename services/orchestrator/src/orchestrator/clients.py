"""Client seams for the components the Orchestrator calls.

Each is a Protocol so a real HTTP client can swap in later. For the Phase-1 stub
the defaults are in-process fakes returning canned results — so the orchestration
spine runs end to end with no running services and no live LearnCard. The real
Context Builder (#20), Profile Resolver (#51) and Delivery Router (#56) plug in
here over HTTP when their service URLs are configured (see app.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from orchestrator.schemas import DeliveryPhasePlan, GateDecision


@dataclass(frozen=True)
class EnvelopeContext:
    """Correlation envelope the delivery-service seams require (#25 design §4).
    Phase 1 runs one workflow per execution, so ``workflow_id == execution_id``."""

    workflow_id: str
    execution_id: str
    correlation_id: str
    delivery_config_ref: str


class ContextBuilderClient(Protocol):
    def build_context(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]: ...


class ProfileResolverClient(Protocol):
    def resolve(
        self, learner_id_type: str, learner_id_value: str, ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]: ...


class FieldMappingClient(Protocol):
    def map(
        self, request: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]: ...


class FieldSynthesisClient(Protocol):
    def synthesize(
        self, transformation_type: str, synthesis_request: dict[str, Any], ctx: EnvelopeContext
    ) -> dict[str, Any]: ...


class DeliveryRouterClient(Protocol):
    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]: ...


class StubContextBuilder:
    """Canned context bundle, loosely mirroring the real Context Builder's shape."""

    def build_context(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]:
        metadata = event.get("metadata", {})
        return {
            "execution_id": execution_id,
            "event_type": metadata.get("event_name"),
            "source_data": {
                "outcome": {
                    "title": "1.0.0 Sample Competency",
                    "display_name": "Demonstrate the sample competency",
                    "description": "Stubbed outcome supplied by the Context Builder seam.",
                },
                "learner_profile": {"email": f"{metadata.get('user_id', 'learner')}@example.com"},
            },
        }


class StubProfileResolver:
    """Canned LearnCard profile (the real resolver — #51 — searches/stores one)."""

    def resolve(
        self, learner_id_type: str, learner_id_value: str, ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        handle = (learner_id_value or "learner").lower()
        return {
            "profile_id": f"@{handle}",
            "did": f"did:web:network.learncard.com:users:{handle}",
            "resolution_method": "stubbed",
        }


class StubFieldMapping:
    """Phase-1 Field Mapping stub: the §10 envelope with null refs (every field
    maps directly, so no placeholders / synthesis). Behaviorally identical to the
    pre-#27 inline stub; used when no field_mapping_url is configured."""

    def map(self, request: dict[str, Any], ctx: EnvelopeContext, step_id: str) -> dict[str, Any]:
        return {
            "status": "succeeded",
            "mapping_artifact_ref": None,
            "synthesis_request_ref": None,
            "requires_synthesis": False,
            "llm_invocation_log_ref": None,
        }


class StubFieldSynthesis:
    """Phase-1 Field Synthesis stub: no synthesized values (the stub mapping
    requires no synthesis). Used when no field_synthesis_url is configured."""

    def synthesize(
        self, transformation_type: str, synthesis_request: dict[str, Any], ctx: EnvelopeContext
    ) -> dict[str, Any]:
        return {"status": "succeeded", "values": {}}


class StubDeliveryRouter:
    """Canned delivery results (the real router — #56 — calls LearnCard adapters)."""

    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        if action == "issue_learncard_badge":
            unsigned = payload.get("unsigned_vc", {})
            signed = {**unsigned, "proof": {"type": "stub", "jws": "stub-signature"}}
            return {
                "status": "succeeded",
                "action": action,
                "external_reference_id": "stub-issued",
                "result": {"issued_credential": signed},
            }
        if action == "deliver_to_learncard_wallet":
            return {
                "status": "succeeded",
                "action": action,
                "external_reference_id": "stub-delivered",
                "result": {"delivery_state": "accepted"},
            }
        if action == "deliver_to_smartresume":
            return {
                "status": "succeeded",
                "action": action,
                "external_reference_id": "stub-smartresume",
                "result": {"redirect_url": "https://mock.smartresume.example/createmyresume/stub"},
            }
        return {
            "status": "failed",
            "action": action,
            "error": {"message": f"unknown action: {action}"},
        }


class HttpContextBuilderClient:
    """Real Context Builder client — POSTs to its /build-context. The CB returns
    either a bundle or a failure response (both 200); the executor path inspects
    the body, so this just returns the parsed JSON."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)

    def build_context(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(
            "/build-context", json={"execution_id": execution_id, "event": event}
        )
        body: dict[str, Any] = resp.json()
        return body


# The router routes by action, but the request envelope also declares the adapter.
_ADAPTER_KEY_BY_ACTION = {
    "issue_learncard_badge": "learncard_issuer",
    "deliver_to_learncard_wallet": "learncard_wallet",
}


class HttpProfileResolverClient:
    """Real Profile Resolver client (#51) — POSTs the #25 envelope to
    /resolve-learncard-profile. On success returns the inner ``result`` (the
    shape the executor threads downstream); an unresolved/failed resolution is
    surfaced as a failed step so the executor short-circuits the workflow."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)

    def resolve(
        self, learner_id_type: str, learner_id_value: str, ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/resolve-learncard-profile",
            json={
                "contract_version": "v1",
                "workflow_id": ctx.workflow_id,
                "execution_id": ctx.execution_id,
                "step_id": step_id,
                "correlation_id": ctx.correlation_id,
                "delivery_config_ref": ctx.delivery_config_ref,
                "payload": {
                    "learner_id_type": learner_id_type,
                    "learner_id_value": learner_id_value,
                },
            },
        )
        # The resolver returns unresolved/failed as a 200 status envelope; a non-2xx
        # means the service itself is down/misconfigured — let it fail the step.
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        if body.get("status") == "succeeded":
            result: dict[str, Any] = body["result"]
            return result
        return {
            "status": "failed",
            "error": body.get("error") or {"message": f"profile {body.get('status')}"},
        }


class HttpDeliveryRouterClient:
    """Real Delivery Router client (#56) — POSTs the #25 envelope to
    /delivery-actions and passes the normalized response straight back (the
    executor inspects ``status`` and the actions read ``result``)."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)

    def dispatch(
        self, action: str, payload: dict[str, Any], ctx: EnvelopeContext, step_id: str
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/delivery-actions",
            json={
                "action": action,
                "contract_version": "v1",
                "adapter_key": _ADAPTER_KEY_BY_ACTION[action],
                "workflow_id": ctx.workflow_id,
                "execution_id": ctx.execution_id,
                "step_id": step_id,
                "correlation_id": ctx.correlation_id,
                "delivery_config_ref": ctx.delivery_config_ref,
                "payload": payload,
            },
        )
        # The router normalizes adapter/transport failures to a 200 status envelope;
        # a non-2xx means the router itself is down/misconfigured — fail the step.
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body


class HttpFieldMappingClient:
    """Real Field Mapping client (#27) — POSTs a MappingRequest to /map and returns
    the §10 response envelope. The caller (actions._generate_payload_mapping) treats
    the result as best-effort: a failure does not fail the workflow, because the
    deterministic obv3 stand-in still produces the delivered payload (build item 8).
    ``execution_id`` / ``event_id`` are filled from the correlation envelope."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=60.0)

    def map(self, request: dict[str, Any], ctx: EnvelopeContext, step_id: str) -> dict[str, Any]:
        resp = self._client.post(
            "/map",
            json={
                "execution_id": ctx.execution_id,
                "event_id": ctx.correlation_id,
                **request,
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body


class HttpFieldSynthesisClient:
    """Real Field Synthesis client (#85) — POSTs to /synthesize-fields with the
    synthesis-request artifact inline (the two services keep separate artifact
    stores, so a ref would not resolve) and returns the response envelope, which
    carries the generated ``values`` inline. Best-effort: the caller falls back to
    empty synthesized values on failure, so a Field Synthesis outage does not fail
    the workflow (the obv3 stand-in still delivers)."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=60.0)

    def synthesize(
        self, transformation_type: str, synthesis_request: dict[str, Any], ctx: EnvelopeContext
    ) -> dict[str, Any]:
        resp = self._client.post(
            "/synthesize-fields",
            json={
                "execution_id": ctx.execution_id,
                "event_id": ctx.correlation_id,
                "transformation_type": transformation_type,
                "synthesis_request": synthesis_request,
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body


# --- LLM Decision Service planner seams (#27 / ADR-0007) ---
# When their URLs are configured the planner path calls these real services;
# otherwise the engine falls back to the deterministic planner stubs. The engine
# treats them as best-effort — a failure falls back rather than failing the
# workflow (the deterministic plan still runs).


class DeliveryTargetsClient(Protocol):
    def select_targets(
        self,
        event_type: str,
        source_system: str,
        learner_context: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> list[str]: ...


class WorkflowActionsClient(Protocol):
    def pre_target_gate(
        self,
        event_type: str,
        event: dict[str, Any],
        context_bundle: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> GateDecision: ...

    def delivery_phase_plan(
        self,
        event_type: str,
        source_system: str,
        selected_targets: list[str],
        event: dict[str, Any],
        context_bundle: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> DeliveryPhasePlan: ...


class HttpDeliveryTargetsClient:
    """Real Delivery Targets LLM Decision Service (#77) — POSTs to
    /select-delivery-targets and returns the flat selected-targets list."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=60.0)

    def select_targets(
        self,
        event_type: str,
        source_system: str,
        learner_context: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> list[str]:
        resp = self._client.post(
            "/select-delivery-targets",
            json={
                "execution_id": ctx.execution_id,
                "event_id": ctx.correlation_id,
                "event_type": event_type,
                "source_system": source_system,
                "learner_context": learner_context,
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        if body.get("status") != "succeeded":
            raise RuntimeError(f"delivery-targets returned {body.get('status')}")
        targets: list[str] = list(body["selected_targets"])
        return targets


class HttpWorkflowActionsClient:
    """Real Workflow Actions LLM Decision Service (#78) — the two-stage planner.
    The gate service returns a discriminated ``decision`` string; we normalize it
    to the Orchestrator's continue/terminate Literal, preserving the specific
    terminate reason in the rationale."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=60.0)

    def pre_target_gate(
        self,
        event_type: str,
        event: dict[str, Any],
        context_bundle: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> GateDecision:
        resp = self._client.post(
            "/pre-target-gate",
            json={
                "execution_id": ctx.execution_id,
                "event_id": ctx.correlation_id,
                "event_type": event_type,
                "event": event,
                "context_bundle": context_bundle,
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        if body.get("status") != "succeeded":
            raise RuntimeError(f"workflow-actions gate returned {body.get('status')}")
        raw = str(body.get("decision") or "terminate")
        rationale = str(body.get("rationale") or "")
        if raw == "continue_to_delivery_targets":
            return GateDecision(decision="continue_to_delivery_targets",
                                confidence=body.get("confidence", 1.0), rationale=rationale)
        # Any terminate_* reason maps to the orchestrator's "terminate" Literal.
        return GateDecision(decision="terminate", confidence=body.get("confidence", 1.0),
                            rationale=f"{raw}: {rationale}" if rationale else raw)

    def delivery_phase_plan(
        self,
        event_type: str,
        source_system: str,
        selected_targets: list[str],
        event: dict[str, Any],
        context_bundle: dict[str, Any],
        ctx: EnvelopeContext,
    ) -> DeliveryPhasePlan:
        resp = self._client.post(
            "/delivery-phase-plan",
            json={
                "execution_id": ctx.execution_id,
                "event_id": ctx.correlation_id,
                "event_type": event_type,
                "source_system": source_system,
                "event": event,
                "context_bundle": context_bundle,
                "selected_targets": selected_targets,
            },
        )
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        if body.get("status") != "succeeded" or not body.get("plan"):
            raise RuntimeError(f"workflow-actions plan returned {body.get('status')}")
        return DeliveryPhasePlan(**body["plan"])
