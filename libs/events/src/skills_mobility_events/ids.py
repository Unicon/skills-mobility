"""Identifier and timestamp helpers for emitted events.

Each emission gets a fresh ``event_id`` and ``emission_id``; a single trigger
(one ``/demo/emit`` call, or one scenario run) gets one ``correlation_id`` that
is stamped onto every event it produces. This is what makes a scenario both
repeatable (fresh ids each run) and traceable (stable correlation per trigger).
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_event_id() -> str:
    """Unique id for a single emitted event."""
    return _uid("evt")


def new_emission_id() -> str:
    """Unique id for a single emission record (log entry)."""
    return _uid("emis")


def new_correlation_id() -> str:
    """One id per trigger; shared across all events of a scenario run."""
    return _uid("corr")


def now_utc() -> datetime:
    """Current time, timezone-aware UTC."""
    return datetime.now(UTC)
