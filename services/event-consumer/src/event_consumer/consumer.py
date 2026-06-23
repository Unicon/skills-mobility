"""Ingress logic: validate → derive identity → idempotency claim → create the
initial execution + capture the Orchestrator handoff."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from event_consumer import identity
from event_consumer.handoff import CaptureHandoff, Handoff
from event_consumer.store import SqliteStore


@dataclass
class IngestResult:
    status: str  # "created" | "duplicate" | "rejected"
    execution_id: str | None = None
    errors: list[str] | None = None


def _new_execution_id() -> str:
    return "exec_" + uuid.uuid4().hex[:12]


def process(
    event: dict[str, Any], store: SqliteStore, handoff: Handoff | None = None
) -> IngestResult:
    errors = identity.validate(event)
    if errors:
        store.record_rejection(identity.rejection_key(event), errors)
        return IngestResult(status="rejected", errors=errors)

    metadata = event.get("metadata", {})
    key = identity.identity_key(event)
    etype = identity.event_type(event) or ""
    correlation_id = metadata.get("correlation_id", "")
    execution_id = _new_execution_id()

    existing = store.claim_identity(key, execution_id, etype, correlation_id)
    if existing is not None:
        return IngestResult(status="duplicate", execution_id=existing)

    store.create_execution(execution_id, metadata.get("event_id", ""), correlation_id, etype)
    (handoff or CaptureHandoff(store)).hand_off(execution_id, event)
    return IngestResult(status="created", execution_id=execution_id)
