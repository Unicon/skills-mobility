"""Client seams for the components the Orchestrator calls.

Each is a Protocol so a real HTTP client can swap in later. For the Phase-1 stub
the defaults are in-process fakes returning canned results — so the orchestration
spine runs end to end with no running services and no live LearnCard. The real
Context Builder (#20) and the #19 delivery services plug in here when wired.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class ContextBuilderClient(Protocol):
    def build_context(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]: ...


class ProfileResolverClient(Protocol):
    def resolve(self, learner_id: str) -> dict[str, Any]: ...


class DeliveryRouterClient(Protocol):
    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]: ...


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
    """Canned LearnCard profile (the real resolver — #19 — searches/creates one)."""

    def resolve(self, learner_id: str) -> dict[str, Any]:
        handle = (learner_id or "learner").lower()
        return {
            "profile_id": f"@{handle}",
            "did": f"did:web:network.learncard.com:users:{handle}",
            "resolution_method": "stubbed",
        }


class StubDeliveryRouter:
    """Canned delivery results (the real router — #19 — calls LearnCard adapters)."""

    def dispatch(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
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
