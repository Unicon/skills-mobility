"""Execution-state store (ADR-0014: SQLite locally; design §9).

Three tables: ``workflow_execution`` (one row per run), ``workflow_step_execution``
(one row per executed step), and the reusable ``workflow_plan`` store. Step
payloads are kept inline as JSON for the POC (FR-OR-21 permits inline storage);
the AWS-shaped target moves large artifacts out-of-line.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from orchestrator.schemas import (
    DeliveryPhasePlan,
    ExecutionMetadata,
    ExecutionSummary,
    GateDecision,
    StepProgress,
    StepResult,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_execution (
    execution_id         TEXT PRIMARY KEY,
    event_id             TEXT,
    correlation_id       TEXT,
    event_type           TEXT,
    status               TEXT NOT NULL,
    gate_decision        TEXT,
    plan_id              TEXT,
    context_artifact_ref TEXT,
    result               TEXT,
    created_at           TEXT NOT NULL,
    updated_at           TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_step_execution (
    execution_id TEXT NOT NULL,
    step_id      INTEGER NOT NULL,
    action_id    TEXT NOT NULL,
    status       TEXT NOT NULL,
    attempt      INTEGER NOT NULL DEFAULT 1,
    output_json  TEXT,
    error_json   TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    PRIMARY KEY (execution_id, step_id)
);
CREATE TABLE IF NOT EXISTS workflow_plan (
    plan_id           TEXT PRIMARY KEY,
    applicability_key TEXT,
    plan_json         TEXT NOT NULL,
    created_at        TEXT NOT NULL,
    last_used_at      TEXT,
    updated_at        TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ExecutionStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- workflow_execution -------------------------------------------------

    def create_execution(
        self, execution_id: str, event_id: str, correlation_id: str, event_type: str
    ) -> None:
        now = _now()
        self._conn.execute(
            "INSERT OR REPLACE INTO workflow_execution "
            "(execution_id, event_id, correlation_id, event_type, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'created', ?, ?)",
            (execution_id, event_id, correlation_id, event_type, now, now),
        )
        self._conn.commit()

    def set_status(self, execution_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE workflow_execution SET status = ?, updated_at = ? WHERE execution_id = ?",
            (status, _now(), execution_id),
        )
        self._conn.commit()

    def record_gate_decision(self, execution_id: str, gate: GateDecision) -> None:
        self._conn.execute(
            "UPDATE workflow_execution SET gate_decision = ?, updated_at = ? "
            "WHERE execution_id = ?",
            (gate.model_dump_json(), _now(), execution_id),
        )
        self._conn.commit()

    def set_plan(self, execution_id: str, plan_id: str) -> None:
        self._conn.execute(
            "UPDATE workflow_execution SET plan_id = ?, updated_at = ? WHERE execution_id = ?",
            (plan_id, _now(), execution_id),
        )
        self._conn.commit()

    def set_result(self, execution_id: str, result: dict[str, Any]) -> None:
        self._conn.execute(
            "UPDATE workflow_execution SET result = ?, updated_at = ? WHERE execution_id = ?",
            (json.dumps(result), _now(), execution_id),
        )
        self._conn.commit()

    # --- workflow_step_execution -------------------------------------------

    def save_step(self, execution_id: str, step: StepResult) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO workflow_step_execution "
            "(execution_id, step_id, action_id, status, attempt, output_json, error_json, "
            "started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execution_id,
                step.step_id,
                step.action_id,
                step.status,
                step.attempt,
                json.dumps(step.output),
                json.dumps(step.error) if step.error is not None else None,
                step.started_at,
                step.finished_at,
            ),
        )
        self._conn.commit()

    # --- workflow_plan (reusable) ------------------------------------------

    def save_plan(self, plan: DeliveryPhasePlan, applicability_key: str) -> None:
        now = _now()
        self._conn.execute(
            "INSERT OR REPLACE INTO workflow_plan "
            "(plan_id, applicability_key, plan_json, created_at, last_used_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (plan.plan_id, applicability_key, plan.model_dump_json(), now, now, now),
        )
        self._conn.commit()

    def get_plan_by_key(self, applicability_key: str) -> DeliveryPhasePlan | None:
        row = self._conn.execute(
            "SELECT plan_json FROM workflow_plan WHERE applicability_key = ?", (applicability_key,)
        ).fetchone()
        if row is None:
            return None
        return DeliveryPhasePlan.model_validate_json(row["plan_json"])

    def delete_plan(self, plan_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM workflow_plan WHERE plan_id = ?", (plan_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # --- read model ---------------------------------------------------------

    def get_execution_metadata(self, execution_id: str) -> ExecutionMetadata | None:
        row = self._conn.execute(
            "SELECT * FROM workflow_execution WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        step_rows = self._conn.execute(
            "SELECT * FROM workflow_step_execution WHERE execution_id = ? ORDER BY step_id",
            (execution_id,),
        ).fetchall()
        steps = [
            StepResult(
                step_id=s["step_id"],
                action_id=s["action_id"],
                status=s["status"],
                attempt=s["attempt"],
                output=json.loads(s["output_json"]) if s["output_json"] else {},
                error=json.loads(s["error_json"]) if s["error_json"] else None,
                started_at=s["started_at"] or "",
                finished_at=s["finished_at"] or "",
            )
            for s in step_rows
        ]
        return ExecutionMetadata(
            execution_id=row["execution_id"],
            correlation_id=row["correlation_id"] or "",
            event_type=row["event_type"],
            status=row["status"],
            gate_decision=json.loads(row["gate_decision"]) if row["gate_decision"] else None,
            plan_id=row["plan_id"],
            steps=steps,
            result=json.loads(row["result"]) if row["result"] else {},
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

    def list_executions(
        self, limit: int = 50, correlation_id: str | None = None
    ) -> list[ExecutionSummary]:
        """Recent executions (newest first), optionally filtered to one Action
        run's correlation id. Compact rows with completed/total step counts
        computed server-side (#28 G1/G2/G6)."""
        sql = (
            "SELECT e.execution_id, e.correlation_id, e.event_type, e.status, "
            "e.created_at, e.updated_at, "
            "(SELECT COUNT(*) FROM workflow_step_execution s "
            " WHERE s.execution_id = e.execution_id) AS total, "
            "(SELECT COUNT(*) FROM workflow_step_execution s "
            " WHERE s.execution_id = e.execution_id AND s.status = 'succeeded') AS completed "
            "FROM workflow_execution e "
        )
        params: list[Any] = []
        if correlation_id is not None:
            sql += "WHERE e.correlation_id = ? "
            params.append(correlation_id)
        sql += "ORDER BY e.updated_at DESC, e.execution_id DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [
            ExecutionSummary(
                execution_id=r["execution_id"],
                correlation_id=r["correlation_id"] or "",
                event_type=r["event_type"],
                status=r["status"],
                step_progress=StepProgress(completed=r["completed"], total=r["total"]),
                created_at=r["created_at"] or "",
                updated_at=r["updated_at"] or "",
            )
            for r in rows
        ]
