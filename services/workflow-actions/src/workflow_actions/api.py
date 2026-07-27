"""FastAPI boundary for the Workflow Actions service.

Two endpoints:
  POST /pre-target-gate  (GateRequest -> GateResponse)
  POST /delivery-phase-plan  (PlanRequest -> PlanResponse)
  GET  /healthz
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from .config import Settings, get_settings
from .contracts import GateRequest, GateResponse, PlanRequest, PlanResponse
from .llm_adapter import LLMAdapter
from .plan_store import PlanStore
from .replay_adapter import ReplayAdapter
from .service import WorkflowActionsService


def build_service(
    settings: Settings, *, adapter: LLMAdapter | None = None
) -> WorkflowActionsService:
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
            raise ValueError(
                f"adapter mode '{settings.mode}' is not implemented (use 'replay' or 'bedrock')"
            )
    return WorkflowActionsService(
        settings=settings,
        adapter=adapter,
        plan_store=PlanStore(Path(settings.artifact_dir)),
    )


def create_app(service: WorkflowActionsService | None = None) -> FastAPI:
    svc = service or build_service(get_settings())
    app = FastAPI(title="Workflow Actions LLM Decision Service")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/pre-target-gate")
    def pre_target_gate_endpoint(request: GateRequest) -> GateResponse:
        return svc.run_gate(request)

    @app.post("/delivery-phase-plan")
    def delivery_phase_plan_endpoint(request: PlanRequest) -> PlanResponse:
        return svc.generate_plan(request)

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(), host="0.0.0.0", port=settings.port)
