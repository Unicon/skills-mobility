"""FastAPI application factory for the Mock LMS / Mock Event Producer."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from mock_lms.api import emit, metadata, stream
from mock_lms.config import Settings, get_settings
from mock_lms.emission import EmissionLog, EventBridgeEmitter, LocalEmitter
from mock_lms.scenarios import load_store


def _build_emitter(settings: Settings) -> LocalEmitter | EventBridgeEmitter:
    if settings.emitter == "eventbridge":
        return EventBridgeEmitter(settings.event_bus_name, settings.aws_region)
    return LocalEmitter()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Mock LMS / Event Producer",
        version="0.1.0",
        summary="Canvas-style mock LMS metadata APIs + credential event emission (POC)",
    )
    app.state.settings = settings
    app.state.store = load_store(settings.fixtures_dir)
    app.state.emitter = _build_emitter(settings)
    app.state.emission_log = EmissionLog(capacity=settings.emission_log_capacity)

    app.include_router(metadata.router)
    app.include_router(emit.router)
    app.include_router(stream.router)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "emitter": app.state.emitter.target}

    return app


def run() -> None:  # pragma: no cover - console entrypoint
    import uvicorn

    uvicorn.run("mock_lms.app:create_app", factory=True, host="127.0.0.1", port=8000)
