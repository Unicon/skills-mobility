"""FastAPI application for the Transformation Executor.

One request = one JSONata execution.  Applies the supplied mapping expression to
the assembled source payloads and synthesized values, returns a normalized result.
All failures normalize to ``status: "failed"`` (HTTP 200) so the Orchestrator
always gets the executor contract back.  Emits a structured log line per execution
(the Orchestrator owns the persisted correlated execution view, per ADR-0016).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from transformation_executor import executor
from transformation_executor.config import Settings, get_settings
from transformation_executor.contracts import ExecutionRequest, ExecutionResponse

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Transformation Executor",
        version="0.1.0",
        summary="Apply a JSONata mapping expression to assembled credential payloads (POC)",
    )
    app.state.settings = settings

    @app.post("/execute")
    def execute(request: ExecutionRequest) -> ExecutionResponse:
        response = executor.run(request)
        if response.status == "succeeded" and response.result is not None:
            logger.info(
                "execution execution_id=%s event_id=%s correlation_id=%s "
                "transformation_type=%s status=%s output_keys=%d",
                request.execution_id,
                request.event_id,
                request.correlation_id,
                request.transformation_type,
                response.status,
                len(response.result),
            )
        else:
            error_type = response.error.error_type if response.error else "unknown"
            logger.info(
                "execution execution_id=%s event_id=%s correlation_id=%s "
                "transformation_type=%s status=%s error_type=%s",
                request.execution_id,
                request.event_id,
                request.correlation_id,
                request.transformation_type,
                response.status,
                error_type,
            )
        return response

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so the executor's INFO logs are emitted (uvicorn
    # doesn't do this for app loggers). Level via TRANSFORMATION_EXECUTOR_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
