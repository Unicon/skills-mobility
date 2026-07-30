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

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from orchestrator import obv3
from orchestrator.clients import (
    DeliveryRouterClient,
    EnvelopeContext,
    FieldMappingClient,
    FieldSynthesisClient,
    ProfileResolverClient,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ActionDeps:
    profile_resolver: ProfileResolverClient
    delivery_router: DeliveryRouterClient
    field_mapping: FieldMappingClient
    field_synthesis: FieldSynthesisClient
    issuer_id: str
    envelope: EnvelopeContext


def _resolve_learncard_profile(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    return deps.profile_resolver.resolve(
        inputs.get("learner_id_type", "profile_id"),
        inputs.get("learner_id_value", ""),
        deps.envelope,
        "resolve_learncard_profile",
    )


_DEGRADED_MAPPING = {
    "status": "succeeded",
    "mapping_artifact_ref": None,
    "synthesis_request_ref": None,
    "requires_synthesis": False,
    "llm_invocation_log_ref": None,
}


def _mapping_source_payloads(inputs: dict[str, Any]) -> dict[str, Any]:
    """Assemble the phase's source_payloads for the Field Mapping request (#27 §4).
    Aliases settled on #33: `profile_resolution` (recipient/issuer ids) plus, for
    the issuer phase, the Context Builder source_data; for the wallet phase, the
    issued badge."""
    profile = inputs.get("resolved_profile", {})
    profile_resolution = {
        "recipient_did": profile.get("did"),
        "recipient_profile_id": profile.get("profile_id"),
        "issuer_id": inputs.get("issuer_id"),
    }
    if inputs.get("transformation_type") == "wallet_payload":
        issued = inputs.get("issued", {})
        signed = (issued.get("result") or {}).get("issued_credential", {})
        return {"issued_badge": signed, "profile_resolution": profile_resolution}
    source_data = (inputs.get("bundle") or {}).get("source_data", {})
    payloads = {**source_data, "profile_resolution": profile_resolution}
    # Issuer phase reads the stored credential template as a source artifact
    # (ADR-0017: Phase 2 depends on Phase 1's output).
    template = (inputs.get("credential_template") or {}).get("credential_template")
    if template:
        payloads["credential_template"] = template
    return payloads


def _generate_payload_mapping(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Field Mapping seam (#27). Calls the Field Mapping service (or the Phase-1
    stub when no URL is configured) and returns its §10 response envelope.
    ``transformation_type`` / ``delivery_target`` are independent plan literals
    (#27 §4); ``requires_synthesis`` is derived by the service, never asserted here.

    Best-effort (build item 8): the deterministic obv3 stand-in still produces the
    delivered payload, so a Field Mapping failure must NOT fail the workflow — we
    log it and return a non-fatal succeeded/null-refs envelope. Wiring the mapping
    artifact into delivery needs the Transformation Executor + Field Synthesis
    (not yet built)."""
    request = {
        "transformation_type": inputs.get("transformation_type"),
        "delivery_target": inputs.get("delivery_target"),
        "synthesis_allowed": bool(inputs.get("synthesis_allowed", False)),
        "source_system": inputs.get("source_system", "mock_lms"),
        "fetch_profile_id": inputs.get("fetch_profile_id", "skill_mastered.v1"),
        "source_payloads": _mapping_source_payloads(inputs),
    }
    if request["delivery_target"] is None:
        # credential_template is target-independent: the FM contract wants the
        # field absent (not null) for that phase.
        request.pop("delivery_target")
    try:
        result = deps.field_mapping.map(request, deps.envelope, "generate_payload_mapping")
    except Exception as err:
        logger.warning("field mapping call failed (non-fatal; obv3 stand-in delivers): %s", err)
        return dict(_DEGRADED_MAPPING)
    if result.get("status") != "succeeded":
        logger.warning("field mapping returned failed (non-fatal): %s", result.get("status"))
        return dict(_DEGRADED_MAPPING)
    return result


def _generate_field_synthesis(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    """Field Synthesis seam (#27/#85). When the Field Mapping result marked fields
    for synthesis, call the Field Synthesis service with the synthesis-request
    artifact the mapping response carries inline (the two services keep separate
    artifact stores, so the orchestrator passes it inline rather than by ref) and
    return the produced values for the Translation Executor to merge under
    ``synthesized.*``.

    Best-effort: no synthesis required, a missing client, or a failed call all
    yield empty synthesized values rather than failing the workflow (the obv3
    stand-in still delivers)."""
    mapping = inputs.get("mapping") or {}
    if not mapping.get("requires_synthesis"):
        return {"synthesized": {}}
    synthesis_request = mapping.get("synthesis_request")
    if not synthesis_request:
        logger.warning("field mapping required synthesis but returned no inline request")
        return {"synthesized": {}}
    transformation_type = str(inputs.get("transformation_type") or "issuer_payload")
    try:
        result = deps.field_synthesis.synthesize(
            transformation_type, synthesis_request, deps.envelope
        )
    except Exception as err:
        logger.warning("field synthesis call failed (non-fatal; no synthesized values): %s", err)
        return {"synthesized": {}}
    if result.get("status") != "succeeded":
        logger.warning("field synthesis returned failed (non-fatal): %s", result.get("status"))
        return {"synthesized": {}}
    # Preserve the response envelope alongside the merged values: confidence and
    # rationale must stay recoverable from the execution record (FR-FS-9, design
    # §12 "inline always"), and the refs give the audit trail a pointer to the
    # stored artifacts — parity with the mapping seam, which persists its whole
    # envelope as the step output.
    return {
        "synthesized": result.get("values") or {},
        "confidence": result.get("confidence"),
        "rationale": result.get("rationale"),
        "synthesis_result_ref": result.get("synthesis_result_ref"),
        "llm_invocation_log_ref": result.get("llm_invocation_log_ref"),
    }


def _execute_credential_template_translation(
    inputs: dict[str, Any], deps: ActionDeps
) -> dict[str, Any]:
    """Credential-template Translation Executor (ADR-0017 Phase 1). The Phase-1
    stand-in derives the achievement definition (name / description / criteria)
    deterministically from the context bundle; the issuer phase reads it as a
    source artifact (via _mapping_source_payloads)."""
    source = (inputs.get("bundle") or {}).get("source_data", {})
    outcome = source.get("outcome") or {}
    name = outcome.get("display_name") or outcome.get("title") or "Credential"
    description = outcome.get("description") or f"Demonstrated mastery: {name}."
    return {
        "credential_template": {
            "name": name,
            "description": description,
            "criteria": {"narrative": outcome.get("description") or f"Awarded for {name}."},
        }
    }


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


def _execute_smartresume_payload_translation(
    inputs: dict[str, Any], deps: ActionDeps
) -> dict[str, Any]:
    """SmartResume-side Translation Executor — the wallet_payload-equivalent phase
    keyed to smart_resume (ADR-0017 / phase-2 §2). The Phase-1 stand-in builds the
    CredentialConnect payload from the ISSUED credential (LearnCard issues every
    credential first) + the resolved profile + learner contact from the bundle."""
    issued = (inputs.get("issued", {}).get("result") or {}).get("issued_credential") or {}
    ob3 = dict(issued)
    # SmartResume requires a top-level credential id; stamp a deterministic one
    # if issuance didn't assign it (stubbed issuance returns the unsigned VC).
    ob3.setdefault("id", f"urn:poc:credential:{deps.envelope.execution_id}")
    resolved_profile = inputs["resolved_profile"]
    learner = (inputs["bundle"].get("source_data") or {}).get("learner_profile") or {}
    email = learner.get("email", "")
    recipient: dict[str, Any] = {
        "id": resolved_profile.get("did") or f"mailto:{email}",
        "email": email,
    }
    if learner.get("givenName"):
        recipient["givenName"] = learner["givenName"]
    if learner.get("familyName"):
        recipient["familyName"] = learner["familyName"]
    return {"recipient": recipient, "credentials": [ob3]}


def _deliver_to_smartresume(inputs: dict[str, Any], deps: ActionDeps) -> dict[str, Any]:
    return deps.delivery_router.dispatch(
        "deliver_to_smartresume",
        inputs["smartresume_payload"],
        deps.envelope,
        "deliver_to_smartresume",
    )


Action = Callable[[dict[str, Any], ActionDeps], dict[str, Any]]

ACTIONS: dict[str, Action] = {
    "resolve_learncard_profile": _resolve_learncard_profile,
    "generate_credential_template_mapping": _generate_payload_mapping,
    "generate_credential_template_synthesis": _generate_field_synthesis,
    "execute_credential_template_translation": _execute_credential_template_translation,
    "generate_issuer_payload_mapping": _generate_payload_mapping,
    "generate_issuer_payload_synthesis": _generate_field_synthesis,
    "execute_issuer_payload_translation": _execute_issuer_payload_translation,
    "issue_learncard_badge": _issue_learncard_badge,
    "generate_learncard_wallet_payload_mapping": _generate_payload_mapping,
    "execute_learncard_wallet_payload_translation": _execute_wallet_payload_translation,
    "deliver_to_learncard_wallet": _deliver_to_learncard_wallet,
    "generate_smartresume_payload_mapping": _generate_payload_mapping,
    "execute_smartresume_payload_translation": _execute_smartresume_payload_translation,
    "deliver_to_smartresume": _deliver_to_smartresume,
}
