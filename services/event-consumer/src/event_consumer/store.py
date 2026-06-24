"""Local SQLite store (ADR-0014). Keeps the logical split the AWS target uses:
an idempotency table, a workflow-execution table, and — in capture mode, until
the Orchestrator exists — an orchestrator-outbox table. The same boundary maps
to DynamoDB tables in AWS.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingress_idempotency (
    identity_key  TEXT PRIMARY KEY,
    execution_id  TEXT,
    event_type    TEXT,
    correlation_id TEXT,
    status        TEXT NOT NULL,
    first_seen    TEXT NOT NULL,
    detail        TEXT
);
CREATE TABLE IF NOT EXISTS workflow_execution (
    execution_id    TEXT PRIMARY KEY,
    source_event_id TEXT,
    correlation_id  TEXT,
    event_type      TEXT,
    status          TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orchestrator_outbox (
    execution_id TEXT PRIMARY KEY,
    envelope     TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    captured     INTEGER NOT NULL DEFAULT 1
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SqliteStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def claim_identity(
        self, identity_key: str, execution_id: str, event_type: str, correlation_id: str
    ) -> str | None:
        """Atomically claim the identity. Returns ``None`` if newly claimed, or
        the existing execution id if this event was already seen (duplicate)."""
        try:
            self._conn.execute(
                "INSERT INTO ingress_idempotency "
                "(identity_key, execution_id, event_type, correlation_id, status, first_seen) "
                "VALUES (?, ?, ?, ?, 'claimed', ?)",
                (identity_key, execution_id, event_type, correlation_id, _now()),
            )
            self._conn.commit()
            return None
        except sqlite3.IntegrityError:
            row = self._conn.execute(
                "SELECT execution_id FROM ingress_idempotency WHERE identity_key = ?",
                (identity_key,),
            ).fetchone()
            return row["execution_id"] if row else None

    def create_execution(
        self, execution_id: str, source_event_id: str, correlation_id: str, event_type: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO workflow_execution "
            "(execution_id, source_event_id, correlation_id, event_type, status, created_at) "
            "VALUES (?, ?, ?, ?, 'created', ?)",
            (execution_id, source_event_id, correlation_id, event_type, _now()),
        )
        self._conn.commit()

    def set_status(self, execution_id: str, status: str) -> None:
        """Advance the workflow status (e.g. ``handoff_captured`` / ``handoff_sent``)."""
        self._conn.execute(
            "UPDATE workflow_execution SET status = ? WHERE execution_id = ?",
            (status, execution_id),
        )
        self._conn.commit()

    def capture_handoff(self, execution_id: str, envelope: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO orchestrator_outbox (execution_id, envelope, created_at) VALUES (?, ?, ?)",
            (execution_id, json.dumps(envelope), _now()),
        )
        self._conn.commit()

    def record_rejection(self, key: str, errors: list[str]) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO ingress_idempotency "
            "(identity_key, execution_id, event_type, correlation_id, status, first_seen, detail) "
            "VALUES (?, NULL, NULL, NULL, 'rejected', ?, ?)",
            (key, _now(), json.dumps(errors)),
        )
        self._conn.commit()

    def reset(self) -> int:
        """Clear ingress + execution + outbox state so a demo can re-run
        (FR-EC-23). Returns the number of idempotency records cleared."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM ingress_idempotency").fetchone()
        cleared = row["n"]
        self._conn.execute("DELETE FROM ingress_idempotency")
        self._conn.execute("DELETE FROM workflow_execution")
        self._conn.execute("DELETE FROM orchestrator_outbox")
        self._conn.commit()
        return int(cleared)

    # --- inspection (FR-EC-18/19/20) ---
    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM workflow_execution WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_handoff(self, execution_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM orchestrator_outbox WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["envelope"] = json.loads(out["envelope"])
        return out
