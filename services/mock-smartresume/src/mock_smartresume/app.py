"""FastAPI application factory for the Mock SmartResume."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from mock_smartresume.api import credentials, health, token
from mock_smartresume.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Mock SmartResume",
        version="0.1.0",
        summary="Deterministic offline stand-in for the SmartResume CredentialConnect API (POC)",
    )
    app.state.settings = settings

    app.include_router(token.router)
    app.include_router(credentials.router)
    app.include_router(health.router)

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so app logs are emitted. Level via
    # MOCK_SMARTRESUME_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
