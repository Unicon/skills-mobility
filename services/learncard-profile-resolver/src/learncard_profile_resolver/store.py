"""Mapping store: learner identifier -> LearnCard profile (design §6).

Pluggable — the resolution flow depends only on the ``MappingStore`` shape, so a
DynamoDB implementation can replace the SQLite one without touching resolver.py.
Composite key ``{learner_id_type}#{learner_id_value}`` mirrors the DynamoDB `pk`.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import Protocol

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_mapping (
    pk                TEXT PRIMARY KEY,
    profile_id        TEXT NOT NULL,
    did               TEXT NOT NULL,
    resolved_at       TEXT NOT NULL,
    resolution_method TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _pk(id_type: str, id_value: str) -> str:
    return f"{id_type}#{id_value}"


class MappingStore(Protocol):
    def get(self, id_type: str, id_value: str) -> dict[str, str] | None: ...

    def put(
        self, id_type: str, id_value: str, profile_id: str, did: str, resolution_method: str
    ) -> None: ...


class SqliteMappingStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def get(self, id_type: str, id_value: str) -> dict[str, str] | None:
        row = self._conn.execute(
            "SELECT profile_id, did FROM profile_mapping WHERE pk = ?",
            (_pk(id_type, id_value),),
        ).fetchone()
        return {"profile_id": row["profile_id"], "did": row["did"]} if row else None

    def put(
        self, id_type: str, id_value: str, profile_id: str, did: str, resolution_method: str
    ) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO profile_mapping "
            "(pk, profile_id, did, resolved_at, resolution_method) VALUES (?, ?, ?, ?, ?)",
            (_pk(id_type, id_value), profile_id, did, _now(), resolution_method),
        )
        self._conn.commit()
