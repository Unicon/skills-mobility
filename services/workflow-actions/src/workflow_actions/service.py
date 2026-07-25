"""The Workflow Actions service pipeline (design §3 / §8).

Two stages, both following: screen -> prompt -> adapter -> validate ->
store -> response. Exactly one model attempt per stage (no hidden repair retry).

Stage 1 — pre-target gate:
  Store the invocation log (NOT a reusable artifact); return decision inline.

Stage 2 — delivery-phase plan:
  Store the plan artifact + invocation log; return plan inline (+ plan_ref).
"""

from __future__ import annotations

import datetime
from typing import Any

from .action_registry_view import gating_prose, prompt_projection, valid_action_pairs
from .contracts import (
    DeliveryPhasePlan,
    GateRequest,
    GateResponse,
    PlanApplicability,
    PlanGenerator,
    PlanRequest,
    PlanResponse,
)
from .llm_adapter import LLMAdapter
from .plan_store import PlanStore
from .prompt_builder import GATE_PROMPT_VERSION, PLAN_PROMPT_VERSION
from .validators import WORKFLOW_CONTEXT_KEYS, validate_gate, validate_plan

_SERVICE_VERSION = "workflow-actions.v1"


class WorkflowActionsService:
    def __init__(
        self,
        *,
        settings: Any,
        adapter: LLMAdapter,
        plan_store: PlanStore,
    ) -> None:
        self._settings = settings
        self._adapter = adapter
        self._plan_store = plan_store

    def run_gate(self, request: GateRequest) -> GateResponse:
        prose = gating_prose()

        # Exactly one attempt; no repair retry.
        generation, meta = self._adapter.gate(request, gating_prose=prose)
        errors = validate_gate(generation)

        log_ref = self._plan_store.store_invocation_log(
            _gate_invocation_log(request, generation, meta, errors, self._settings),
            key=f"gate-{request.execution_id}",
        )

        if errors:
            return GateResponse.failed(llm_invocation_log_ref=log_ref)

        return GateResponse.succeeded(
            decision=generation.decision,
            confidence=generation.confidence,
            rationale=generation.rationale,
            llm_invocation_log_ref=log_ref,
        )

    def generate_plan(self, request: PlanRequest) -> PlanResponse:
        registry = valid_action_pairs()
        registry_view = prompt_projection()

        # Exactly one attempt; no repair retry.
        generation, meta = self._adapter.plan(request, registry_view=registry_view)
        errors = validate_plan(
            generation,
            registry=registry,
            workflow_context_keys=WORKFLOW_CONTEXT_KEYS,
        )

        generated_at = datetime.datetime.now(datetime.UTC).isoformat()
        plan = DeliveryPhasePlan(
            plan_id=_plan_id(request),
            generated_at=generated_at,
            generator=PlanGenerator(
                service_version=_SERVICE_VERSION,
                model_identifier=self._settings.model_id,
                prompt_template_version=PLAN_PROMPT_VERSION,
            ),
            applicability=PlanApplicability(
                event_type=request.event_type,
                source_system=request.source_system,
                selected_targets=list(request.selected_targets),
            ),
            confidence=generation.confidence,
            rationale=generation.rationale,
            steps=generation.steps,
        )

        log_ref = self._plan_store.store_invocation_log(
            _plan_invocation_log(request, generation, meta, errors, self._settings),
            key=f"plan-{request.execution_id}",
        )

        if errors:
            self._plan_store.store_failed(plan, errors)
            return PlanResponse.failed(llm_invocation_log_ref=log_ref)

        plan_ref = self._plan_store.store_plan(plan)
        return PlanResponse.succeeded(
            plan=plan,
            plan_ref=plan_ref,
            confidence=generation.confidence,
            rationale=generation.rationale,
            llm_invocation_log_ref=log_ref,
        )


def _plan_id(request: PlanRequest) -> str:
    targets = ".".join(sorted(request.selected_targets))
    return f"{request.event_type}.{targets}.v1"


# ADR-0010 §60: capture per-invocation model metadata (provider/model/temperature/
# tokens/latency) plus the prompt sent and the structured output, so the audit trail
# shows exactly what the model received and returned. ``model_id`` prefers the meta
# (the model actually used) and falls back to the configured id.
def _gate_invocation_log(
    request: GateRequest,
    generation: Any,
    meta: Any,
    errors: list[str],
    settings: Any,
) -> dict[str, Any]:
    return {
        "service": "workflow-actions",
        "stage": "pre_target_gate",
        "phase": "pre_target_gate",
        "status": "failed" if errors else "succeeded",
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "event_type": request.event_type,
        "provider": meta.provider,
        "model_id": meta.model_id or settings.model_id,
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "decision": generation.decision,
        "confidence": generation.confidence,
        "rationale": generation.rationale,
        "validation_errors": errors,
        "prompt_template_version": GATE_PROMPT_VERSION,
        "corpus_scenario_id": None,
    }


def _plan_invocation_log(
    request: PlanRequest,
    generation: Any,
    meta: Any,
    errors: list[str],
    settings: Any,
) -> dict[str, Any]:
    return {
        "service": "workflow-actions",
        "stage": "delivery_phase_plan",
        "phase": "delivery_phase_plan",
        "status": "failed" if errors else "succeeded",
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "event_type": request.event_type,
        "source_system": request.source_system,
        "selected_targets": list(request.selected_targets),
        "provider": meta.provider,
        "model_id": meta.model_id or settings.model_id,
        "temperature": meta.temperature,
        "input_tokens": meta.input_tokens,
        "output_tokens": meta.output_tokens,
        "latency_ms": meta.latency_ms,
        "system_prompt": meta.system_prompt,
        "user_prompt": meta.user_prompt,
        "confidence": generation.confidence,
        "rationale": generation.rationale,
        "validation_errors": errors,
        "prompt_template_version": PLAN_PROMPT_VERSION,
        "corpus_scenario_id": None,
    }
