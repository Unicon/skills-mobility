"""Orchestrator handoff seam.

Two modes (ADR-0015): capture-mode records the outbound envelope in the local
store for inspection; HTTP-mode POSTs it to the Orchestrator's ``/run-workflow``
trigger when ``EVENT_CONSUMER_ORCHESTRATOR_URL`` is set. ``hand_off`` returns the
workflow status to record (``handoff_captured`` / ``handoff_sent``).
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx

from event_consumer.store import SqliteStore


class Handoff(Protocol):
    def hand_off(self, execution_id: str, event: dict[str, Any]) -> str: ...


class CaptureHandoff:
    """Record the handoff in the local store (no Orchestrator running)."""

    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def hand_off(self, execution_id: str, event: dict[str, Any]) -> str:
        self._store.capture_handoff(execution_id, event)
        return "handoff_captured"


class HttpHandoff:
    """POST the envelope to the Orchestrator's /run-workflow trigger."""

    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=30.0)

    def hand_off(self, execution_id: str, event: dict[str, Any]) -> str:
        resp = self._client.post(
            "/run-workflow", json={"execution_id": execution_id, "event": event}
        )
        resp.raise_for_status()  # surface a non-2xx from the Orchestrator instead of swallowing it
        return "handoff_sent"
