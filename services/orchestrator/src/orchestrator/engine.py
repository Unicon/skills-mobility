"""Orchestration engine — the planner path then the executor path (design §8).

Drives one workflow run: create the execution record, build context, run the
pre-target gate, select targets, obtain the delivery-phase plan (reusable lookup
or stub generation), then execute it. Persistence is threaded through the store
so the run is inspectable step by step.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from orchestrator import planner
from orchestrator.actions import ActionDeps
from orchestrator.clients import (
    ContextBuilderClient,
    DeliveryRouterClient,
    DeliveryTargetsClient,
    EnvelopeContext,
    ProfileResolverClient,
    WorkflowActionsClient,
)
from orchestrator.executor import execute_plan
from orchestrator.schemas import (
    DeliveryPhasePlan,
    ExecutionMetadata,
    GateDecision,
    WorkflowStartRequest,
)
from orchestrator.store import ExecutionStore

logger = logging.getLogger(__name__)


def run_workflow(
    request: WorkflowStartRequest,
    *,
    store: ExecutionStore,
    context_builder: ContextBuilderClient,
    profile_resolver: ProfileResolverClient,
    delivery_router: DeliveryRouterClient,
    issuer_id: str,
    delivery_config_ref: str,
    recipient_profile_id: str,
    delivery_targets: DeliveryTargetsClient | None = None,
    workflow_actions: WorkflowActionsClient | None = None,
    reusable_plan_lookup: bool = False,
) -> ExecutionMetadata:
    metadata = request.event.get("metadata", {})
    execution_id = request.execution_id
    event_type = planner.event_type_of(request.event)
    logger.info("workflow start: execution_id=%s event_type=%s", execution_id, event_type)

    store.create_execution(
        execution_id,
        request.event_id or metadata.get("event_id", ""),
        request.correlation_id or metadata.get("correlation_id", ""),
        event_type,
    )
    store.set_status(execution_id, "planning")

    # Planner path: context → pre-target gate → targets → delivery-phase plan.
    bundle = context_builder.build_context(execution_id, request.event)
    if "context_builder_error" in bundle:
        logger.warning("context builder failed: execution_id=%s", execution_id)
        store.set_result(execution_id, {"error": "context_builder_failed"})
        store.set_status(execution_id, "failed")
        return _metadata(store, execution_id)

    envelope = EnvelopeContext(
        workflow_id=execution_id,  # Phase 1: one workflow per execution.
        execution_id=execution_id,
        correlation_id=request.correlation_id or metadata.get("correlation_id", ""),
        delivery_config_ref=delivery_config_ref,
    )
    source_system = str(metadata.get("source_system") or "mock_lms")

    # Pre-target gate — Workflow Actions Stage 1 (best-effort; deterministic fallback).
    gate = _resolve_gate(workflow_actions, event_type, request.event, bundle, envelope)
    store.record_gate_decision(execution_id, gate)
    logger.info("gate decision: execution_id=%s decision=%s", execution_id, gate.decision)
    if gate.decision != "continue_to_delivery_targets":
        store.set_result(
            execution_id, {"outcome": "terminated_before_delivery", "rationale": gate.rationale}
        )
        store.set_status(execution_id, "completed")
        logger.info("workflow terminated pre-delivery: execution_id=%s", execution_id)
        return _metadata(store, execution_id)

    # Delivery target selection (best-effort; deterministic fallback).
    targets = _resolve_targets(delivery_targets, event_type, source_system, bundle, envelope)
    key = planner.applicability_key(event_type, targets)
    plan = store.get_plan_by_key(key) if reusable_plan_lookup else None
    if plan is None:
        # Delivery-phase plan — Workflow Actions Stage 2 (best-effort; deterministic fallback).
        plan = _resolve_plan(
            workflow_actions, event_type, source_system, targets, request.event, bundle,
            datetime.now(UTC).isoformat(), envelope,
        )
        store.save_plan(plan, key)
        logger.info("delivery-phase plan generated: execution_id=%s plan_id=%s", execution_id,
                    plan.plan_id)
    else:
        logger.info("delivery-phase plan reused: execution_id=%s plan_id=%s", execution_id,
                    plan.plan_id)
    store.set_plan(execution_id, plan.plan_id)
    store.set_status(execution_id, "ready")

    # Executor path.
    workflow_ctx = {
        "event": request.event,
        "bundle": bundle,
        "issuer_id": issuer_id,
        "delivery_config_ref": delivery_config_ref,
        # POC resolves + delivers to the fixed demo recipient wallet, not the event's
        # learner (ADR-0020); the originating learner stays on the stored event.
        "learner_id_value": recipient_profile_id,
    }
    deps = ActionDeps(
        profile_resolver=profile_resolver,
        delivery_router=delivery_router,
        issuer_id=issuer_id,
        envelope=envelope,
    )
    store.set_status(execution_id, "running")
    status, result = execute_plan(plan, workflow_ctx, deps, store, execution_id)
    store.set_result(execution_id, result)
    store.set_status(execution_id, status)
    logger.info("workflow %s: execution_id=%s", status, execution_id)
    return _metadata(store, execution_id)


def _resolve_gate(
    wa: WorkflowActionsClient | None,
    event_type: str,
    event: dict[str, Any],
    bundle: dict[str, Any],
    ctx: EnvelopeContext,
) -> GateDecision:
    """Workflow Actions pre-target gate, best-effort: fall back to the deterministic
    gate if the service is unconfigured or the call fails (keeps the workflow running)."""
    if wa is not None:
        try:
            return wa.pre_target_gate(event_type, event, bundle, ctx)
        except Exception as err:  # noqa: BLE001 — best-effort seam
            logger.warning("workflow-actions gate failed (non-fatal; deterministic gate): %s", err)
    return planner.pre_target_gate(event_type)


def _resolve_targets(
    dt: DeliveryTargetsClient | None,
    event_type: str,
    source_system: str,
    bundle: dict[str, Any],
    ctx: EnvelopeContext,
) -> list[str]:
    """Delivery Targets selection, best-effort: fall back to the deterministic
    fixed target set if unconfigured or the call fails."""
    if dt is not None:
        try:
            return dt.select_targets(event_type, source_system, bundle, ctx)
        except Exception as err:  # noqa: BLE001 — best-effort seam
            logger.warning("delivery-targets failed (non-fatal; deterministic targets): %s", err)
    return planner.select_delivery_targets()


def _resolve_plan(
    wa: WorkflowActionsClient | None,
    event_type: str,
    source_system: str,
    targets: list[str],
    event: dict[str, Any],
    bundle: dict[str, Any],
    generated_at: str,
    ctx: EnvelopeContext,
) -> DeliveryPhasePlan:
    """Workflow Actions delivery-phase plan, best-effort: fall back to the
    deterministic plan if unconfigured or the call fails/returns an invalid plan."""
    if wa is not None:
        try:
            return wa.delivery_phase_plan(event_type, source_system, targets, event, bundle, ctx)
        except Exception as err:  # noqa: BLE001 — best-effort seam
            logger.warning("workflow-actions plan failed (non-fatal; deterministic plan): %s", err)
    return planner.delivery_phase_plan(event_type, targets, generated_at)


def _metadata(store: ExecutionStore, execution_id: str) -> ExecutionMetadata:
    meta = store.get_execution_metadata(execution_id)
    assert meta is not None  # just created in this call
    return meta
