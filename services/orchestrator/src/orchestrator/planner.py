"""Planner path artifacts (ADR-0009 two-stage hierarchical model).

Phase 1 satisfies the Workflow Actions / Delivery Targets seams with deterministic
stubs, but returns the *intended* target-PoC artifact shapes (FR-OR-5): a
pre-target gate decision and a delivery-phase plan. Swapping in the real LLM
Decision Services later is a planner change, not an executor change.
"""

from __future__ import annotations

from typing import Any

from orchestrator.schemas import (
    DeliveryPhasePlan,
    GateDecision,
    InputBinding,
    PlanApplicability,
    PlanGenerator,
    PlanStep,
)

# Canvas Live Event names → the logical event types Phase 1 supports (FR-OR-9).
_EVENT_TYPE_BY_NAME = {
    "learning_outcome_result_created": "skill_mastered",
    "course_completed": "course_completed",
}
_SUPPORTED = frozenset(_EVENT_TYPE_BY_NAME.values())
_PHASE1_TARGETS = ["learncard_issuer", "learncard_wallet"]
# The deterministic Context Builder fetch profile per event type — supplied to the
# Field Mapping seam so it resolves its source catalogs (#27 §4/§5).
_FETCH_PROFILE_BY_EVENT = {
    "skill_mastered": "skill_mastered.v1",
    "course_completed": "course_completed.v1",
}

_WALLET_TARGET = "learncard_wallet"
_SMARTRESUME_TARGET = "smart_resume"


def event_type_of(event: dict[str, Any]) -> str:
    name = str(event.get("metadata", {}).get("event_name", ""))
    return _EVENT_TYPE_BY_NAME.get(name, name)


def pre_target_gate(event_type: str) -> GateDecision:
    """Stage-1 Workflow Actions stub: continue for the supported happy paths,
    terminate otherwise (FR-OR-10)."""
    if event_type in _SUPPORTED:
        return GateDecision(
            decision="continue",
            rationale="Deterministic Phase 1 happy-path gate decision.",
        )
    return GateDecision(
        decision="terminate",
        rationale=f"Unsupported event type for Phase 1: {event_type or '(unknown)'}.",
    )


def select_delivery_targets() -> list[str]:
    """Delivery Targets stub: always LearnCard issuance + wallet (FR-OR-11)."""
    return list(_PHASE1_TARGETS)


def applicability_key(event_type: str, targets: list[str]) -> str:
    """Reusable-plan lookup key — event type + selected targets (ADR-0011)."""
    return f"{event_type}|{','.join(sorted(targets))}"


def _step(step_id: int, action_id: str, inputs: dict[str, InputBinding], produces: str) -> PlanStep:
    return PlanStep(step_id=step_id, action_id=action_id, inputs=inputs, produces=produces)


def _issuer_prefix(fetch_profile_id: str) -> list[PlanStep]:
    """Shared transformation prefix (steps 1-8), always emitted: resolve profile,
    then the credential_template phase (ADR-0017 Phase 1 — the achievement
    definition the issuer phase reads as a source artifact), then the
    issuer_payload phase, then badge issuance. Field Mapping / Field Synthesis
    seams are preserved as explicit steps (FR-OR-14/15); mapping steps carry the
    source_system + fetch_profile_id + upstream data the Field Mapping service
    needs (#27 §4)."""
    return [
        _step(
            1,
            "resolve_learncard_profile",
            {
                # Resolve by LearnCard handle, not email: LearnCard Search doesn't
                # match email and services can't create profiles, so the POC delivers
                # to a fixed pre-provisioned recipient wallet (ADR-0020, #41).
                "learner_id_type": InputBinding(source="literal", value="profile_id"),
                "learner_id_value": InputBinding(source="workflow", path="learner_id_value"),
                "delivery_config_ref": InputBinding(source="workflow", path="delivery_config_ref"),
            },
            "resolved_profile",
        ),
        _step(
            2,
            "generate_credential_template_mapping",
            {
                # credential_template is target-independent (ADR-0017 Phase 1), so
                # no delivery_target literal is bound (the FM contract wants the
                # field absent for this phase).
                "transformation_type": InputBinding(source="literal", value="credential_template"),
                "synthesis_allowed": InputBinding(source="literal", value=True),
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
            },
            "credential_template_mapping",
        ),
        _step(
            3,
            "generate_credential_template_synthesis",
            {
                "transformation_type": InputBinding(source="literal", value="credential_template"),
                "mapping": InputBinding(source="step", step_id=2),
            },
            "credential_template_synthesis",
        ),
        _step(
            4,
            "execute_credential_template_translation",
            {
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
                "mapping": InputBinding(source="step", step_id=2),
                "synthesis": InputBinding(source="step", step_id=3),
            },
            "credential_template",
        ),
        _step(
            5,
            "generate_issuer_payload_mapping",
            {
                # transformation_type and delivery_target are independent plan
                # literals, not a derived pair (#27 §4); synthesis_allowed is the
                # plan's permission gate for Field Synthesis this phase (#27 §6).
                "transformation_type": InputBinding(source="literal", value="issuer_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "synthesis_allowed": InputBinding(source="literal", value=True),
                # Source resolution + payload inputs for the Field Mapping request.
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
                # The stored credential template is a source artifact for the
                # issuer mapping (ADR-0017: Phase 2 reads Phase 1's output).
                "credential_template": InputBinding(source="step", step_id=4),
            },
            "issuer_mapping",
        ),
        _step(
            6,
            "generate_issuer_payload_synthesis",
            {
                "transformation_type": InputBinding(source="literal", value="issuer_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "mapping": InputBinding(source="step", step_id=5),
            },
            "issuer_synthesis",
        ),
        _step(
            7,
            "execute_issuer_payload_translation",
            {
                "bundle": InputBinding(source="workflow", path="bundle"),
                "issuer_id": InputBinding(source="workflow", path="issuer_id"),
                "resolved_profile": InputBinding(source="step", step_id=1),
                # Seam bindings for the real transformation services (Phase-1 stubs
                # ignore them, but the executor wiring must be in place — FR-OR-14).
                "delivery_target": InputBinding(source="literal", value="learncard_issuer"),
                "mapping": InputBinding(source="step", step_id=5),
                "synthesis": InputBinding(source="step", step_id=6),
            },
            "issuer_payload",
        ),
        _step(
            8,
            "issue_learncard_badge",
            {"issuer_payload": InputBinding(source="step", step_id=7)},
            "issued",
        ),
    ]


def _wallet_delivery_steps(fetch_profile_id: str) -> list[PlanStep]:
    """LearnCard wallet delivery steps (9-11), emitted when learncard_wallet is in
    the selected targets."""
    return [
        _step(
            9,
            "generate_learncard_wallet_payload_mapping",
            {
                # The wallet phase provisions no Field Synthesis step, so the plan
                # passes synthesis_allowed=false — a property of this plan, not a
                # rule hardcoded in the FM service or the executor (#27 §6).
                "transformation_type": InputBinding(source="literal", value="wallet_payload"),
                "delivery_target": InputBinding(source="literal", value="learncard_wallet"),
                "synthesis_allowed": InputBinding(source="literal", value=False),
                # Source resolution + the issued badge for the Field Mapping request.
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "issued": InputBinding(source="step", step_id=8),
                "resolved_profile": InputBinding(source="step", step_id=1),
            },
            "wallet_mapping",
        ),
        _step(
            10,
            "execute_learncard_wallet_payload_translation",
            {
                "issued": InputBinding(source="step", step_id=8),
                "resolved_profile": InputBinding(source="step", step_id=1),
                # Seam bindings for the real transformation services (FR-OR-15) —
                # wallet pass has no synthesis (per the #25 FR-OR-15 table).
                "delivery_target": InputBinding(source="literal", value="learncard_wallet"),
                "mapping": InputBinding(source="step", step_id=9),
            },
            "wallet_payload",
        ),
        _step(
            11,
            "deliver_to_learncard_wallet",
            {"wallet_payload": InputBinding(source="step", step_id=10)},
            "delivered",
        ),
    ]


def _smartresume_delivery_steps(fetch_profile_id: str, start_id: int) -> list[PlanStep]:
    """SmartResume delivery steps (mapping → translation → deliver), emitted when
    smart_resume is in the selected targets. Runs after issuance (LearnCard issues
    every credential first); the SmartResume payload is translated from the issued
    badge (the wallet_payload-equivalent phase keyed to smart_resume)."""
    return [
        _step(
            start_id,
            "generate_smartresume_payload_mapping",
            {
                "transformation_type": InputBinding(source="literal", value="wallet_payload"),
                "delivery_target": InputBinding(source="literal", value="smart_resume"),
                "synthesis_allowed": InputBinding(source="literal", value=False),
                "source_system": InputBinding(source="literal", value="mock_lms"),
                "fetch_profile_id": InputBinding(source="literal", value=fetch_profile_id),
                "issued": InputBinding(source="step", step_id=8),
                "resolved_profile": InputBinding(source="step", step_id=1),
            },
            "smartresume_mapping",
        ),
        _step(
            start_id + 1,
            "execute_smartresume_payload_translation",
            {
                "issued": InputBinding(source="step", step_id=8),
                "resolved_profile": InputBinding(source="step", step_id=1),
                "bundle": InputBinding(source="workflow", path="bundle"),
                "delivery_target": InputBinding(source="literal", value="smart_resume"),
                "mapping": InputBinding(source="step", step_id=start_id),
            },
            "smartresume_payload",
        ),
        _step(
            start_id + 2,
            "deliver_to_smartresume",
            {"smartresume_payload": InputBinding(source="step", step_id=start_id + 1)},
            "delivered_smartresume",
        ),
    ]


def _build_steps(fetch_profile_id: str, targets: frozenset[str]) -> list[PlanStep]:
    """Assemble the step list based on selected targets.

    - The shared prefix (steps 1-8) is always included: resolve profile, the
      credential_template phase (ADR-0017 Phase 1), the issuer_payload phase, and
      badge issuance — LearnCard is the only issuer, so every credential is issued
      through it and the selected targets decide only the final delivery step(s)
      (design §5 — learncard_issuer is expected in every selection).
    - Wallet delivery (steps 9-11) when learncard_wallet is in targets, or when no
      known delivery target is present (backward-compatible Phase-1 default).
    - SmartResume delivery (3 steps, starting at 12 if the wallet branch is present,
      else 9) when smart_resume is in targets.
    """
    steps = _issuer_prefix(fetch_profile_id)

    has_wallet = _WALLET_TARGET in targets
    has_smartresume = _SMARTRESUME_TARGET in targets
    # Backward-compatible default: emit the wallet branch if no known final
    # delivery target is requested.
    emit_wallet = has_wallet or not (has_wallet or has_smartresume)

    if emit_wallet:
        steps.extend(_wallet_delivery_steps(fetch_profile_id))

    if has_smartresume:
        start_id = 12 if emit_wallet else 9
        steps.extend(_smartresume_delivery_steps(fetch_profile_id, start_id))

    return steps


def _action_templates(
    event_type: str, targets: list[str]
) -> dict[str, tuple[dict[str, tuple[str, ...]], str]]:
    """Derive per-action binding templates from the deterministic planner.

    Builds the deterministic reference plan for the **selected** delivery targets
    — not a superset of every known target — and indexes it by action_id. So an
    LLM-proposed action belonging to a target that was not selected (e.g. a
    ``smart_resume`` action when Delivery Targets chose against SmartResume) finds
    no template and forces a fallback: the Delivery Targets decision is honored
    during re-binding, not bypassed (ADR-0022, #93). Each entry is
    ``(input_template, produces)`` where ``input_template`` maps each input name to
    a spec tuple:

    - ``("step", <produces-name>)`` — resolved from the step that produces that name
    - ``("literal", value)`` — a plan literal
    - ``("workflow", path)`` — a workflow-context path

    Returns ``dict[action_id, (input_template, produces)]``.
    """
    reference_plan = delivery_phase_plan(event_type, targets, "")
    # Build step_id → produces map so step-source bindings can be resolved by name.
    id_to_produces = {s.step_id: s.produces for s in reference_plan.steps if s.produces}

    templates: dict[str, tuple[dict[str, tuple[str, ...]], str]] = {}
    for step in reference_plan.steps:
        input_template: dict[str, tuple[str, ...]] = {}
        for name, binding in step.inputs.items():
            if binding.source == "step":
                dep_produces = id_to_produces.get(binding.step_id or -1, "")
                input_template[name] = ("step", dep_produces)
            elif binding.source == "literal":
                input_template[name] = ("literal", binding.value)
            else:  # workflow
                input_template[name] = ("workflow", binding.path or "")
        templates[step.action_id] = (input_template, step.produces or "")
    return templates


def rebind_plan(
    llm_plan: DeliveryPhasePlan, event_type: str, targets: list[str]
) -> DeliveryPhasePlan | None:
    """Re-bind the LLM's action sequence to executor-compatible step_id bindings.

    The LLM owns action selection, order, and which steps to skip — this reads only
    each step's ``action_id`` and rebuilds every input from a static per-action
    template, so the LLM's own ``inputs``/``step_id`` values (if any) are ignored,
    not corrected. The orchestrator owns the bindings, derived from the deterministic
    reference plan for the **selected** ``targets``, resolving cross-step dependencies
    by produced-name.

    Returns the re-bound plan, or ``None`` if re-binding fails: an unknown action_id
    (including an action for a target that was not selected), or an unsatisfied
    cross-step dependency in the LLM's ordering.
    """
    templates = _action_templates(event_type, targets)
    produced: dict[str, int] = {}  # produced-name → new step_id
    new_steps: list[PlanStep] = []

    for i, step in enumerate(llm_plan.steps, start=1):
        tmpl = templates.get(step.action_id)
        if tmpl is None:
            return None  # unknown action
        input_template, tmpl_produces = tmpl

        inputs: dict[str, InputBinding] = {}
        for name, spec in input_template.items():
            if spec[0] == "step":
                dep_name = spec[1]
                if dep_name not in produced:
                    return None  # dependency not yet satisfied
                inputs[name] = InputBinding(source="step", step_id=produced[dep_name])
            elif spec[0] == "literal":
                inputs[name] = InputBinding(source="literal", value=spec[1])
            else:  # workflow
                inputs[name] = InputBinding(source="workflow", path=spec[1])

        new_steps.append(
            PlanStep(step_id=i, action_id=step.action_id, inputs=inputs, produces=tmpl_produces)
        )
        produced[tmpl_produces] = i

    return llm_plan.model_copy(update={"steps": new_steps})


def delivery_phase_plan(
    event_type: str, targets: list[str], generated_at: str
) -> DeliveryPhasePlan:
    """Stage-2 Workflow Actions stub: the delivery-phase plan for the selected
    targets (FR-OR-12). Same step structure for both supported event types."""
    target_set = frozenset(targets)
    if target_set:
        plan_id = f"phase1-{event_type}.{'.'.join(sorted(target_set))}.v1"
    else:
        plan_id = f"phase1-{event_type}.v1"
    fetch_profile_id = _FETCH_PROFILE_BY_EVENT.get(event_type, f"{event_type}.v1")
    return DeliveryPhasePlan(
        plan_id=plan_id,
        generated_at=generated_at,
        generator=PlanGenerator(
            service_version="phase1-workflow-actions-stub.v1",
            prompt_template_version="phase1-static-plan.v1",
        ),
        applicability=PlanApplicability(event_type=event_type, selected_targets=list(targets)),
        rationale="Deterministic Phase 1 LearnCard workflow.",
        steps=_build_steps(fetch_profile_id, target_set),
    )
