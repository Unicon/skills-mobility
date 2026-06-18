"""Event emitters — the single place that writes to the bus.

``LocalEmitter`` captures envelopes in-process (dev/tests, no AWS);
``EventBridgeEmitter`` is the AWS path (stubbed until infra lands — design §5.2,
build step 6). The persistent, cross-system emission view is the Admin UI's job
(reading the Orchestrator's execution log per the boundary matrix), so there is
no emission log here.
"""

from __future__ import annotations

from typing import Protocol

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
    """AWS EventBridge emitter (PutEvents). Stubbed until infra lands (design §5.2)."""

    def __init__(self, bus_name: str, region: str) -> None:
        self.target = f"eventbridge:{bus_name}"
        self._bus_name = bus_name
        self._region = region

    def emit(self, envelope: LiveEventEnvelope) -> None:  # pragma: no cover - not wired yet
        raise NotImplementedError(
            "EventBridgeEmitter is not wired yet; use MOCK_LMS_EMITTER=local for the POC."
        )
