"""Execution-log store (ADR-0014: SQLite locally). Persists the correlated
per-workflow execution record the Admin UI will later read."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from orchestrator.schemas import ExecutionRecord

_SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
    execution_id TEXT PRIMARY KEY,
    event_type   TEXT,
    status       TEXT NOT NULL,
    record       TEXT NOT NULL,
    recorded_at  TEXT NOT NULL
);
"""


class ExecutionStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save(self, record: ExecutionRecord) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO executions "
            "(execution_id, event_type, status, record, recorded_at) VALUES (?, ?, ?, ?, ?)",
            (
                record.execution_id,
                record.event_type,
                record.status,
                record.model_dump_json(),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._conn.commit()

    def get(self, execution_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT record FROM executions WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        record: dict[str, Any] = json.loads(row["record"])
        return record
