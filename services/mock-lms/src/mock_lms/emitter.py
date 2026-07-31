"""Event emitters — the single place that writes to the bus.

``LocalEmitter`` captures envelopes in-process (dev/tests, no AWS);
``EventBridgeEmitter`` is the AWS path (stubbed until infra lands — design §5.2,
build step 6). The persistent, cross-system emission view is the Admin UI's job
(reading the Orchestrator's execution log per the boundary matrix), so there is
no emission log here.
"""

from __future__ import annotations

from typing import Protocol

import httpx
from skills_mobility_events import LiveEventEnvelope


class Emitter(Protocol):
    target: str

    def emit(self, envelope: LiveEventEnvelope) -> None: ...

    def reset_downstream(self) -> dict[str, str]: ...


class LocalEmitter:
    """Captures emitted envelopes in process. The default for dev and tests.

    When ``forward_url`` is set it also POSTs each envelope to the Event
    Consumer's ``/ingest`` — the local stand-in for the EventBridge → Lambda
    trigger (ADR-0015). In-process capture is retained either way so tests and
    the UI reset can still read ``emitted``.
    """

    target = "local-bus"

    def __init__(
        self, forward_url: str | None = None, client: httpx.Client | None = None
    ) -> None:
        self.emitted: list[LiveEventEnvelope] = []
        self._client = client or (
            httpx.Client(base_url=forward_url, timeout=30.0) if forward_url else None
        )

    def emit(self, envelope: LiveEventEnvelope) -> None:
        self.emitted.append(envelope)
        if self._client is not None:
            self._client.post("/ingest", json=envelope.model_dump(mode="json"))

    def reset_downstream(self) -> dict[str, str]:
        """Cascade a demo reset to the Event Consumer (which cascades to the
        Orchestrator). BOTH hops' outcomes are reported, not swallowed — the
        first live run hid a failed orchestrator terminus behind a succeeding
        Event Consumer hop, so reporting only the immediate downstream lies."""
        if self._client is None:
            return {"event_consumer": "not_configured", "orchestrator": "not_configured"}
        try:
            resp = self._client.post("/reset")
            resp.raise_for_status()
        except httpx.HTTPError:
            return {"event_consumer": "unreachable", "orchestrator": "unknown"}
        orchestrator = "unknown"
        try:
            orchestrator = str(resp.json().get("orchestrator", "unknown"))
        except ValueError:
            pass
        return {"event_consumer": "reset", "orchestrator": orchestrator}


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

    def reset_downstream(self) -> dict[str, str]:  # pragma: no cover - not wired yet
        return {"event_consumer": "not_configured", "orchestrator": "not_configured"}
