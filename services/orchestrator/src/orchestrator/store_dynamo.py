"""DynamoDB-backed execution store (ADR-0014 §9) — the Lambda deployment target.

The SQLite ``ExecutionStore`` keeps state in a file, which does not survive across
Lambda instances (the Admin UI polls a possibly-different instance than the one
that ran the workflow). This backend keeps the same interface but persists to a
single DynamoDB table.

Single-table model, one item per logical record, addressed by ``pk``:

* ``EXEC#<execution_id>`` — the whole execution as one JSON document (its steps
  and decisions inline). Written by read-modify-write, which is safe here because
  a single execution is driven to completion within one synchronous invocation;
  the only other reader (the Admin UI) never writes.
* ``PLAN#<plan_id>`` — a reusable delivery-phase plan.

Payloads are stored as a JSON string in ``body`` rather than native attributes so
we never touch DynamoDB's number/empty-string marshaling rules; the few attributes
we query or sort on (``entity``, ``correlation_id``, ``updated_at``,
``applicability_key``) are plain strings alongside.
"""

from __future__ import annotations

import json
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, ConditionBase

from orchestrator.schemas import (
    DecisionArtifact,
    DeliveryPhasePlan,
    ExecutionMetadata,
    ExecutionSummary,
    StepProgress,
    StepResult,
)
from orchestrator.store import _now


def _exec_pk(execution_id: str) -> str:
    return f"EXEC#{execution_id}"


def _plan_pk(plan_id: str) -> str:
    return f"PLAN#{plan_id}"


class DynamoExecutionStore:
    def __init__(self, table_name: str, region: str | None = None) -> None:
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    # --- execution document helpers ----------------------------------------

    def _load(self, execution_id: str) -> dict[str, Any] | None:
        item = self._table.get_item(Key={"pk": _exec_pk(execution_id)}).get("Item")
        if item is None:
            return None
        doc: dict[str, Any] = json.loads(item["body"])
        return doc

    def _save(self, doc: dict[str, Any]) -> None:
        doc["updated_at"] = _now()
        self._table.put_item(
            Item={
                "pk": _exec_pk(doc["execution_id"]),
                "entity": "execution",
                "correlation_id": doc.get("correlation_id") or "",
                "updated_at": doc["updated_at"],
                "body": json.dumps(doc),
            }
        )

    # --- workflow_execution -------------------------------------------------

    def create_execution(
        self, execution_id: str, event_id: str, correlation_id: str, event_type: str
    ) -> None:
        now = _now()
        self._save(
            {
                "execution_id": execution_id,
                "event_id": event_id,
                "correlation_id": correlation_id,
                "event_type": event_type,
                "status": "created",
                "plan_id": None,
                "result": {},
                "decisions": [],
                "steps": {},
                "created_at": now,
                "updated_at": now,
            }
        )

    def set_status(self, execution_id: str, status: str) -> None:
        doc = self._load(execution_id)
        if doc is None:
            return
        doc["status"] = status
        self._save(doc)

    def record_decision(self, execution_id: str, decision: DecisionArtifact) -> None:
        doc = self._load(execution_id)
        if doc is None:
            return
        payload = decision.model_dump()
        payload["created_at"] = decision.created_at or _now()
        doc["decisions"].append(payload)
        self._save(doc)

    def set_plan(self, execution_id: str, plan_id: str) -> None:
        doc = self._load(execution_id)
        if doc is None:
            return
        doc["plan_id"] = plan_id
        self._save(doc)

    def set_result(self, execution_id: str, result: dict[str, Any]) -> None:
        doc = self._load(execution_id)
        if doc is None:
            return
        doc["result"] = result
        self._save(doc)

    # --- workflow_step_execution -------------------------------------------

    def save_step(self, execution_id: str, step: StepResult) -> None:
        doc = self._load(execution_id)
        if doc is None:
            return
        # keyed by step_id → INSERT OR REPLACE semantics (a retry overwrites)
        doc["steps"][str(step.step_id)] = step.model_dump()
        self._save(doc)

    # --- workflow_plan (reusable) ------------------------------------------

    def save_plan(self, plan: DeliveryPhasePlan, applicability_key: str) -> None:
        self._table.put_item(
            Item={
                "pk": _plan_pk(plan.plan_id),
                "entity": "plan",
                "applicability_key": applicability_key,
                "body": plan.model_dump_json(),
            }
        )

    def get_plan_by_key(self, applicability_key: str) -> DeliveryPhasePlan | None:
        items = self._scan(
            Attr("entity").eq("plan") & Attr("applicability_key").eq(applicability_key)
        )
        if not items:
            return None
        return DeliveryPhasePlan.model_validate_json(items[0]["body"])

    def delete_plan(self, plan_id: str) -> bool:
        resp = self._table.delete_item(Key={"pk": _plan_pk(plan_id)}, ReturnValues="ALL_OLD")
        return "Attributes" in resp

    # --- read model ---------------------------------------------------------

    def get_execution_metadata(self, execution_id: str) -> ExecutionMetadata | None:
        doc = self._load(execution_id)
        if doc is None:
            return None
        decisions = [DecisionArtifact(**d) for d in doc["decisions"]]
        steps = [
            StepResult(**s)
            for s in sorted(doc["steps"].values(), key=lambda s: s["step_id"])
        ]
        return ExecutionMetadata(
            execution_id=doc["execution_id"],
            correlation_id=doc.get("correlation_id") or "",
            event_type=doc.get("event_type"),
            status=doc["status"],
            decisions=decisions,
            plan_id=doc.get("plan_id"),
            steps=steps,
            result=doc.get("result") or {},
            created_at=doc.get("created_at") or "",
            updated_at=doc.get("updated_at") or "",
        )

    def list_executions(
        self, limit: int = 50, correlation_id: str | None = None
    ) -> list[ExecutionSummary]:
        cond: ConditionBase = Attr("entity").eq("execution")
        if correlation_id is not None:
            cond = cond & Attr("correlation_id").eq(correlation_id)
        docs = [json.loads(i["body"]) for i in self._scan(cond)]
        docs.sort(key=lambda d: (d.get("updated_at") or "", d["execution_id"]), reverse=True)
        summaries: list[ExecutionSummary] = []
        for doc in docs[:limit]:
            steps = doc.get("steps", {})
            completed = sum(1 for s in steps.values() if s.get("status") == "succeeded")
            total = self._plan_step_count(doc.get("plan_id"), fallback=len(steps))
            summaries.append(
                ExecutionSummary(
                    execution_id=doc["execution_id"],
                    correlation_id=doc.get("correlation_id") or "",
                    event_type=doc.get("event_type"),
                    status=doc["status"],
                    step_progress=StepProgress(completed=completed, total=total),
                    created_at=doc.get("created_at") or "",
                    updated_at=doc.get("updated_at") or "",
                )
            )
        return summaries

    # --- internals ----------------------------------------------------------

    def _plan_step_count(self, plan_id: str | None, fallback: int) -> int:
        """Plan's declared step count (list denominator), falling back to the
        attempted-step count when no plan is on record (FR-AU-23 / FR-OR-29)."""
        if not plan_id:
            return fallback
        item = self._table.get_item(Key={"pk": _plan_pk(plan_id)}).get("Item")
        if item is None:
            return fallback
        return len(json.loads(item["body"]).get("steps", []))

    def reset_executions(self) -> int:
        """Clear all execution items so a demo can re-run cleanly (the terminus
        of the mock-lms → event-consumer → here reset cascade). Plan items
        (``PLAN#`` pk) survive — they're templates, not per-run state (FR-OR-29)."""
        items = self._scan(Attr("entity").eq("execution"))
        # Per-item deletes, NOT batch_writer: the Ops-managed exec role grants
        # item-level CRUD (DeleteItem) but not dynamodb:BatchWriteItem — found
        # live as an AccessDeniedException. Reset volume is demo-scale.
        for item in items:
            self._table.delete_item(Key={"pk": item["pk"]})
        return len(items)

    def _scan(self, filter_expr: ConditionBase) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"FilterExpression": filter_expr}
        while True:
            resp = self._table.scan(**kwargs)
            items.extend(resp.get("Items", []))
            start = resp.get("LastEvaluatedKey")
            if not start:
                return items
            kwargs["ExclusiveStartKey"] = start
