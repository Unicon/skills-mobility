"""FastAPI boundary for the Field Synthesis service: POST /synthesize-fields + /healthz."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from .artifact_store import ArtifactStore
from .config import Settings, get_settings
from .contracts import SynthesisRequest, SynthesisResponse
from .llm_adapter import LLMAdapter
from .replay_adapter import ReplayAdapter
from .service import SynthesisService


def build_service(settings: Settings, *, adapter: LLMAdapter | None = None) -> SynthesisService:
    if adapter is None:
        if settings.mode == "bedrock":
            from .bedrock_adapter import BedrockAdapter

            adapter = BedrockAdapter(
                model_id=settings.model_id,
                region=settings.aws_region,
                max_tokens=settings.max_tokens,
                temperature=settings.temperature,
            )
        elif settings.mode == "replay":
            adapter = ReplayAdapter()
        else:
            raise NotImplementedError(
                f"adapter mode '{settings.mode}' is not implemented (use 'replay' or 'bedrock')"
            )
    return SynthesisService(
        settings=settings,
        artifact_store=ArtifactStore(Path(settings.artifact_dir)),
        adapter=adapter,
    )


def create_app(service: SynthesisService | None = None) -> FastAPI:
    svc = service or build_service(get_settings())
    app = FastAPI(title="Field Synthesis LLM Decision Service")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/synthesize-fields")
    def synthesize_endpoint(request: SynthesisRequest) -> SynthesisResponse:
        return svc.synthesize(request)

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(), host="0.0.0.0", port=settings.port)
