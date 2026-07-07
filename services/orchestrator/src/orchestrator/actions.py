"""Phase-1 action implementations + the step-dispatch map.

The executor stays ignorant of whether an action is a stub or a real service
(design §6); that choice lives here. Each action takes the resolved inputs plus
``ActionDeps`` and returns an opaque output dict. A returned ``status == "failed"``
marks the step (and workflow) failed.

The Field Mapping / Field Synthesis / Translation Executor stubs are shaped to
the Field Mapping service contract (#27 / ADR-0017) so the real services swap in
without reshaping the plan or executor — see the seam notes on each.
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
        inputs.get("learner_id_type", "email"),
        inputs.get("learner_id_value", ""),
        deps.envelope,
        "resolve_learncard_profile",
    )


def _generate_payload_mapping(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Field Mapping seam (#27). Returns the §10 response envelope; the Phase-1
    stub returns the same shape with null artifact refs. ``transformation_type``
    and ``delivery_target`` arrive as independent plan literals (#27 §4) — the stub
    derives neither from the other; the real service uses them to resolve its
    source/target catalogs.

    ``requires_synthesis`` is derived, never asserted (#27 §10):
    ``synthesis_allowed and placeholder_ids and synthesis_request_ref is not None``.
    The stub maps every field directly, so it has no placeholders and no synthesis
    request — the result is always ``False``, honoring the §6 gate for either
    ``synthesis_allowed`` value.

    TODO(#27): when the real service lands, send ``source_payloads`` +
    ``fetch_profile_id`` and return the real ``mapping_artifact_ref`` /
    ``synthesis_request_ref`` / ``llm_invocation_log_ref``."""
    synthesis_allowed = bool(inputs.get("synthesis_allowed", False))
    placeholder_ids: list[str] = []  # Phase-1 stub maps every field directly
    synthesis_request_ref: str | None = None
    requires_synthesis = (
        synthesis_allowed and bool(placeholder_ids) and synthesis_request_ref is not None
    )
    return {
        "status": "succeeded",
        "mapping_artifact_ref": None,
        "synthesis_request_ref": synthesis_request_ref,
        "requires_synthesis": requires_synthesis,
        "llm_invocation_log_ref": None,
    }


def _generate_field_synthesis(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Field Synthesis seam (#27). Returns the flat synthesized-values map the
    Translation Executor merges under ``synthesized.*``. Phase-1: the mapping
    requires no synthesis, so there are no values.

    TODO(#27): when ``requires_synthesis`` is true, call Field Synthesis with the
    mapping's ``synthesis_request_ref`` and return the produced values."""
    return {"synthesized": {}}


def _execute_issuer_payload_translation(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Issuer-side Translation Executor (FR-OR-16). The real executor dereferences
    the mapping's ``mapping_artifact_ref`` → JSONata and runs it over the merged
    ``source_payloads.*`` + ``synthesized.*`` context (#27 §2). The Phase-1 stub's
    mapping carries null refs, so it builds the minimum unsigned OBv3 directly,
    embedding the resolved DID in credentialSubject.id."""
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
    """Wallet-side Translation Executor (FR-OR-17). Same deref/merge contract as
    the issuer side, minus synthesis (the wallet schema accepts OBv3 directly —
    #27 FR-OR-15). Phase-1 stub builds the wallet payload from the issued badge +
    resolved profileId."""
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
    "generate_issuer_payload_mapping": _generate_payload_mapping,
    "generate_issuer_payload_synthesis": _generate_field_synthesis,
    "execute_issuer_payload_translation": _execute_issuer_payload_translation,
    "issue_learncard_badge": _issue_learncard_badge,
    "generate_wallet_payload_mapping": _generate_payload_mapping,
    "execute_wallet_payload_translation": _execute_wallet_payload_translation,
    "deliver_to_learncard_wallet": _deliver_to_learncard_wallet,
}
