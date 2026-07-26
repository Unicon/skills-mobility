"""FastAPI boundary for the Delivery Targets service: POST /select-delivery-targets + /healthz."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from .artifact_store import ArtifactStore
from .catalog_store import CatalogStore
from .config import Settings, get_settings
from .contracts import SelectionRequest, SelectionResponse
from .llm_adapter import LLMAdapter
from .replay_adapter import ReplayAdapter
from .service import SelectionService


def build_service(settings: Settings, *, adapter: LLMAdapter | None = None) -> SelectionService:
    if adapter is None:
        if settings.mode == "bedrock":
            from .bedrock_adapter import BedrockAdapter

            adapter = BedrockAdapter(
                model_id=settings.model_id,
                region=settings.aws_region,
                max_tokens=settings.max_tokens,
            )
        elif settings.mode == "replay":
            adapter = ReplayAdapter()
        else:
            raise NotImplementedError(
                f"adapter mode '{settings.mode}' is not implemented (use 'replay' or 'bedrock')"
            )
    return SelectionService(
        settings=settings,
        catalog_store=CatalogStore(),
        artifact_store=ArtifactStore(Path(settings.artifact_dir)),
        adapter=adapter,
    )


def create_app(service: SelectionService | None = None) -> FastAPI:
    svc = service or build_service(get_settings())
    app = FastAPI(title="Delivery Targets LLM Decision Service")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/select-delivery-targets")
    def select_endpoint(request: SelectionRequest) -> SelectionResponse:
        return svc.select(request)

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(), host="0.0.0.0", port=settings.port)
