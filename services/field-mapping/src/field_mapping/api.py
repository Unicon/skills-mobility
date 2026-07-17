"""FastAPI boundary for the Field Mapping service: POST /map + /healthz."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .artifact_store import ArtifactStore
from .catalog_store import CatalogStore
from .config import Settings, get_settings
from .contracts import MappingRequest, MappingResponse
from .llm_adapter import LLMAdapter
from .replay_adapter import ReplayAdapter, ReplayFixtureNotFoundError
from .service import MappingService


def build_service(settings: Settings, *, adapter: LLMAdapter | None = None) -> MappingService:
    if adapter is None:
        if settings.mode != "replay":
            raise NotImplementedError(
                f"adapter mode '{settings.mode}' is not implemented yet (only 'replay')"
            )
        adapter = ReplayAdapter()
    return MappingService(
        catalog_store=CatalogStore(),
        artifact_store=ArtifactStore(Path(settings.artifact_dir)),
        adapter=adapter,
        reuse_stored=settings.reuse_stored_mapping_artifacts,
        repair_retry=settings.repair_retry_enabled,
    )


def create_app(service: MappingService | None = None) -> FastAPI:
    svc = service or build_service(get_settings())
    app = FastAPI(title="Field Mapping LLM Decision Service")

    @app.exception_handler(ReplayFixtureNotFoundError)
    async def _replay_not_found(
        _req: Request, _exc: ReplayFixtureNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404, content={"detail": "no replay fixture for this request"}
        )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/map")
    def map_endpoint(request: MappingRequest) -> MappingResponse:
        return svc.map(request)

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    # 8120 (enablement layer, near context-builder's 8100) — outside Consul's
    # reserved range 8300-8302/8500/8600 (see #61).
    uvicorn.run(create_app(), host="0.0.0.0", port=8120)
