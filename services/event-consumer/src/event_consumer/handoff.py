"""Orchestrator handoff seam.

Two modes (ADR-0015): capture-mode records the outbound envelope in the local
store for inspection; HTTP-mode POSTs it to the Orchestrator's ``/run-workflow``
trigger when ORCHESTRATOR_URL is set.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from event_consumer.store import SqliteStore


class Handoff(Protocol):
    def hand_off(self, execution_id: str, event: dict[str, Any]) -> None: ...


class CaptureHandoff:
    """Record the handoff in the local store (no Orchestrator running)."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def hand_off(self, execution_id: str, event: dict[str, Any]) -> None:
        self._store.capture_handoff(execution_id, event)


class HttpHandoff:
    """POST the envelope to the Orchestrator's /run-workflow trigger."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)

    def hand_off(self, execution_id: str, event: dict[str, Any]) -> None:
        self._client.post(
            "/run-workflow", json={"execution_id": execution_id, "event": event}
        )
