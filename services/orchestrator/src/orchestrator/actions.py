"""Phase-1 action implementations + the step-dispatch map.

The executor stays ignorant of whether an action is a stub or a real service
(design §6); that choice lives here. Each action takes the resolved inputs plus
``ActionDeps`` and returns an opaque output dict. A returned ``status == "failed"``
marks the step (and workflow) failed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from orchestrator import obv3
from orchestrator.clients import DeliveryRouterClient, EnvelopeContext, ProfileResolverClient


@dataclass(frozen=True)
class ActionDeps:
    profile_resolver: ProfileResolverClient
    delivery_router: DeliveryRouterClient
    issuer_id: str
    envelope: EnvelopeContext


def _resolve_learncard_profile(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    return deps.profile_resolver.resolve(
        inputs.get("learner_id_type", "profile_id"),
        inputs.get("learner_id_value", ""),
        deps.envelope,
        "resolve_learncard_profile",
    )


def _noop(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Field Mapping / Field Synthesis seam — no-op in Phase 1 (FR-OR-14/15)."""
    return {}


def _execute_issuer_payload_translation(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Issuer-side Translation Executor stub: build the minimum unsigned OBv3,
    embedding the resolved DID in credentialSubject.id (FR-OR-16)."""
    recipient_did = inputs["resolved_profile"]["did"]
    unsigned_vc = obv3.build_unsigned_obv3(inputs["bundle"], recipient_did, inputs["issuer_id"])
    return {"unsigned_vc": unsigned_vc}


def _issue_learncard_badge(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    unsigned_vc = inputs["issuer_payload"]["unsigned_vc"]
    return deps.delivery_router.dispatch(
        "issue_learncard_badge",
        {"unsigned_vc": unsigned_vc},
        deps.envelope,
        "issue_learncard_badge",
    )


def _execute_wallet_payload_translation(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Wallet-side Translation Executor stub: the minimum wallet payload from the
    issued badge + resolved profileId (FR-OR-17)."""
    signed_credential = inputs["issued"]["result"]["issued_credential"]
    profile_id = inputs["resolved_profile"]["profile_id"]
    return obv3.prepare_wallet_input(signed_credential, profile_id)


def _deliver_to_learncard_wallet(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    return deps.delivery_router.dispatch(
        "deliver_to_learncard_wallet",
        inputs["wallet_payload"],
        deps.envelope,
        "deliver_to_learncard_wallet",
    )


Action = Callable[[dict[str, Any], ActionDeps], dict[str, Any]]

ACTIONS: dict[str, Action] = {
    "resolve_learncard_profile": _resolve_learncard_profile,
    "generate_issuer_payload_mapping": _noop,
    "generate_issuer_payload_synthesis": _noop,
    "execute_issuer_payload_translation": _execute_issuer_payload_translation,
    "issue_learncard_badge": _issue_learncard_badge,
    "generate_wallet_payload_mapping": _noop,
    "execute_wallet_payload_translation": _execute_wallet_payload_translation,
    "deliver_to_learncard_wallet": _deliver_to_learncard_wallet,
}
