"""Orchestration engine — the planner path then the executor path (design §8).

Drives one workflow run: create the execution record, build context, run the
pre-target gate, select targets, obtain the delivery-phase plan (reusable lookup
or stub generation), then execute it. Persistence is threaded through the store
so the run is inspectable step by step.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from orchestrator import planner
from orchestrator.actions import ActionDeps
from orchestrator.clients import (
    ContextBuilderClient,
    DeliveryRouterClient,
    EnvelopeContext,
    ProfileResolverClient,
)
from orchestrator.executor import execute_plan
from orchestrator.schemas import ExecutionMetadata, WorkflowStartRequest
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

    gate = planner.pre_target_gate(event_type)
    store.record_gate_decision(execution_id, gate)
    logger.info("gate decision: execution_id=%s decision=%s", execution_id, gate.decision)
    if gate.decision != "continue_to_delivery_targets":
        store.set_result(
            execution_id, {"outcome": "terminated_before_delivery", "rationale": gate.rationale}
        )
        store.set_status(execution_id, "completed")
        logger.info("workflow terminated pre-delivery: execution_id=%s", execution_id)
        return _metadata(store, execution_id)

    targets = planner.select_delivery_targets()
    key = planner.applicability_key(event_type, targets)
    plan = store.get_plan_by_key(key) if reusable_plan_lookup else None
    if plan is None:
        plan = planner.delivery_phase_plan(event_type, targets, datetime.now(UTC).isoformat())
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
    envelope = EnvelopeContext(
        workflow_id=execution_id,  # Phase 1: one workflow per execution.
        execution_id=execution_id,
        correlation_id=request.correlation_id or metadata.get("correlation_id", ""),
        delivery_config_ref=delivery_config_ref,
    )
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


def _metadata(store: ExecutionStore, execution_id: str) -> ExecutionMetadata:
    meta = store.get_execution_metadata(execution_id)
    assert meta is not None  # just created in this call
    return meta
