"""FastAPI application factory for the Orchestrator.

`POST /run-workflow` executes the Phase-1 plan and persists the trace;
`GET /executions/{id}` returns the correlated execution record. The downstream
seams default to the Phase-1 stubs (no running services, no live LearnCard).
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException

from orchestrator import runner
from orchestrator.clients import StubContextBuilder, StubDeliveryRouter, StubProfileResolver
from orchestrator.config import Settings, get_settings
from orchestrator.schemas import RunRequest
from orchestrator.store import ExecutionStore


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Orchestrator",
        version="0.1.0",
        summary="Phase-1 deterministic workflow executor (POC)",
    )
    app.state.settings = settings
    app.state.store = ExecutionStore(settings.db_path)
    # Phase-1 stub seams; real HTTP clients swap in when #19's services are built.
    app.state.context_builder = StubContextBuilder()
    app.state.profile_resolver = StubProfileResolver()
    app.state.delivery_router = StubDeliveryRouter()

    @app.post("/run-workflow")
    def run_workflow(request: RunRequest) -> dict[str, Any]:
        record = runner.run_workflow(
            request,
            context_builder=app.state.context_builder,
            profile_resolver=app.state.profile_resolver,
            delivery_router=app.state.delivery_router,
            issuer_id=settings.issuer_id,
        )
        app.state.store.save(record)
        return record.model_dump()

    @app.get("/executions/{execution_id}")
    def get_execution(execution_id: str) -> dict[str, Any]:
        store: ExecutionStore = app.state.store
        record = store.get(execution_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"errors": [{"message": f"execution {execution_id} not found"}]},
            )
        return record

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="127.0.0.1", port=8300)
