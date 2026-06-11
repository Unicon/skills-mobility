"""Event emitters and the in-memory emission log.

The ``Emitter`` is the single place that writes to the bus; everything else
talks to it. ``LocalEmitter`` captures envelopes in-process (dev/tests);
``EventBridgeEmitter`` is the AWS path (stubbed for now — design §6, build
step 6). The ``EmissionLog`` is a bounded buffer that backs the demo UI's
live feed and ``GET /demo/emissions`` backfill.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from skills_mobility_events import LiveEventEnvelope


class Emitter(Protocol):
    target: str

    def emit(self, envelope: LiveEventEnvelope) -> None: ...


class LocalEmitter:
    """Captures emitted envelopes in process. The default for dev and tests."""

    target = "local-bus"

    def __init__(self) -> None:
        self.emitted: list[LiveEventEnvelope] = []

    def emit(self, envelope: LiveEventEnvelope) -> None:
        self.emitted.append(envelope)


class EventBridgeEmitter:
    """AWS EventBridge emitter (PutEvents). Stubbed until infra lands (design §6)."""

    def __init__(self, bus_name: str, region: str) -> None:
        self.target = f"eventbridge:{bus_name}"
        self._bus_name = bus_name
        self._region = region

    def emit(self, envelope: LiveEventEnvelope) -> None:  # pragma: no cover - not wired yet
        raise NotImplementedError(
            "EventBridgeEmitter is not wired yet; use MOCK_LMS_EMITTER=local for the POC."
        )


@dataclass
class EmissionRecord:
    emission_id: str
    correlation_id: str
    event_type: str
    event_name: str
    event_time: datetime
    target: str
    envelope: dict[str, Any]
    scenario_id: str | None = None
    seq: int = field(default=0)

    def to_public_dict(self) -> dict[str, Any]:
        """Shape sent to the UI (both the /demo/emissions backfill and the SSE feed)."""
        return {
            "seq": self.seq,
            "emission_id": self.emission_id,
            "correlation_id": self.correlation_id,
            "scenario_id": self.scenario_id,
            "event_type": self.event_type,
            "event_name": self.event_name,
            "event_time": self.event_time.isoformat(),
            "target": self.target,
            "envelope": self.envelope,
        }


class EmissionLog:
    """Bounded, append-only log with a monotonic cursor for incremental reads."""

    def __init__(self, capacity: int = 500) -> None:
        self._records: deque[EmissionRecord] = deque(maxlen=capacity)
        self._seq = 0

    def append(self, record: EmissionRecord) -> int:
        self._seq += 1
        record.seq = self._seq
        self._records.append(record)
        return self._seq

    def since(self, cursor: int = 0) -> list[EmissionRecord]:
        """Records with seq > cursor, oldest first."""
        return [r for r in self._records if r.seq > cursor]

    @property
    def cursor(self) -> int:
        return self._seq

    def clear(self) -> None:
        self._records.clear()
