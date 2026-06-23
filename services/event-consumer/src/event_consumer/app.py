"""FastAPI application factory for the Event Consumer.

Local ingress stands in for the EventBridge → Lambda trigger (ADR-0015): the
Mock LMS LocalEmitter POSTs envelopes to ``/ingest`` when EVENT_CONSUMER_URL is
set. Malformed envelopes are acked with 422 (not retried); valid ones return the
ingress decision.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from event_consumer import consumer
from event_consumer.config import Settings, get_settings
from event_consumer.handoff import CaptureHandoff, Handoff, HttpHandoff
from event_consumer.store import SqliteStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Event Consumer",
        version="0.1.0",
        summary="Workflow ingress boundary — validate, dedupe, hand off (POC)",
    )
    app.state.settings = settings
    app.state.store = SqliteStore(settings.db_path)
    handoff: Handoff = (
        HttpHandoff(settings.orchestrator_url)
        if settings.orchestrator_url
        else CaptureHandoff(app.state.store)
    )
    app.state.handoff = handoff

    @app.post("/ingest")
    def ingest(event: dict[str, Any]) -> JSONResponse:
        result = consumer.process(event, app.state.store, app.state.handoff)
        if result.status == "rejected":
            return JSONResponse(
                status_code=422, content={"status": "rejected", "errors": result.errors}
            )
        return JSONResponse(
            status_code=200,
            content={"status": result.status, "execution_id": result.execution_id},
        )

    @app.post("/reset", tags=["meta"])
    def reset() -> dict[str, Any]:
        return {"ok": True, "cleared": app.state.store.reset()}

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8200)
