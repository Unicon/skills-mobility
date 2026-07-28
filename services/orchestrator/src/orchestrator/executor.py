"""Executor path (design §8): advance one step at a time, resolve input
bindings, dispatch the bound action, and persist each step result.

For Phase 1 the loop runs synchronously after planning, but each step result is
still persisted as if it were a queue-driven worker transition (FR-OR-8).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from orchestrator.actions import ACTIONS, DEGRADED_KEY, ActionDeps
from orchestrator.schemas import DeliveryPhasePlan, InputBinding, PlanStep, StepResult
from orchestrator.store import ExecutionStoreProtocol

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve(
    value: InputBinding, workflow_ctx: dict[str, Any], outputs: dict[int, dict[str, Any]]
) -> Any:
    if value.source == "literal":
        return value.value
    if value.source == "workflow":
        cur: Any = workflow_ctx
        for part in (value.path or "").split("."):
            cur = cur[part]
        return cur
    if value.source == "step":
        if value.step_id is None:
            raise ValueError("step binding requires step_id")
        return outputs[value.step_id]
    raise ValueError(f"unknown input source: {value.source}")


def _resolve_inputs(
    step: PlanStep, workflow_ctx: dict[str, Any], outputs: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    return {name: _resolve(binding, workflow_ctx, outputs) for name, binding in step.inputs.items()}


def execute_plan(
    plan: DeliveryPhasePlan,
    workflow_ctx: dict[str, Any],
    deps: ActionDeps,
    store: ExecutionStoreProtocol,
    execution_id: str,
) -> tuple[str, dict[str, Any]]:
    """Run the plan's steps in order. Returns ``(workflow_status, result)`` where
    status is ``"completed"`` or ``"failed"``."""
    outputs: dict[int, dict[str, Any]] = {}
    for step in plan.steps:
        started = _now()
        try:
            resolved = _resolve_inputs(step, workflow_ctx, outputs)
            output = ACTIONS[step.action_id](resolved, deps)
        except Exception as exc:  # defensive: an action/binding blew up
            store.save_step(
                execution_id,
                StepResult(
                    step_id=step.step_id,
                    action_id=step.action_id,
                    status="failed",
                    error={"message": str(exc)},
                    started_at=started,
                    finished_at=_now(),
                ),
            )
            return "failed", {}

        # A degraded marker means a best-effort seam fell back (review #102
        # item 2): persist it on the stored step so the audit record shows the
        # degradation, but strip it from the value threaded to downstream steps
        # (delivery payloads must not carry bookkeeping keys).
        degraded = output.pop(DEGRADED_KEY, None)
        failed = output.get("status") == "failed"
        store.save_step(
            execution_id,
            StepResult(
                step_id=step.step_id,
                action_id=step.action_id,
                status="failed" if failed else "succeeded",
                output={**output, DEGRADED_KEY: degraded} if degraded else output,
                error=output.get("error") if failed else None,
                started_at=started,
                finished_at=_now(),
            ),
        )
        logger.info(
            "step %s: execution_id=%s action=%s status=%s",
            step.step_id, execution_id, step.action_id, "failed" if failed else "succeeded",
        )
        if degraded:
            logger.warning(
                "step %s ran degraded: execution_id=%s action=%s reason=%s",
                step.step_id, execution_id, step.action_id, degraded,
            )
        if failed:
            return "failed", {}
        outputs[step.step_id] = output

    return "completed", _assemble_result(plan, outputs)


def _assemble_result(plan: DeliveryPhasePlan, outputs: dict[int, dict[str, Any]]) -> dict[str, Any]:
    by_action = {s.action_id: s.step_id for s in plan.steps}

    def out(action_id: str) -> dict[str, Any]:
        return outputs.get(by_action.get(action_id, -1), {})

    return {
        "recipient_profile_id": out("resolve_learncard_profile").get("profile_id"),
        "issued_ref": out("issue_learncard_badge").get("external_reference_id"),
        "delivery": out("deliver_to_learncard_wallet").get("result"),
    }
