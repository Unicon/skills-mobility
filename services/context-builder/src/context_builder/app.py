"""FastAPI application factory for the Context Builder."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from context_builder.builder import build_context
from context_builder.config import Settings, get_settings
from context_builder.lms_client import HttpxLMSClient
from context_builder.profiles import load_profiles
from context_builder.schemas import BuildRequest


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Context Builder",
        version="0.1.0",
        summary="Deterministic source-data aggregation for the Orchestrator (POC)",
    )
    app.state.settings = settings
    app.state.profiles = load_profiles()
    app.state.lms_client = HttpxLMSClient(settings.lms_base_url)

    @app.post("/build-context")
    def build(request: BuildRequest) -> dict[str, Any]:
        result = build_context(request, app.state.lms_client, app.state.profiles)
        return result.model_dump()

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "profiles": sorted(app.state.profiles)}

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8100)
