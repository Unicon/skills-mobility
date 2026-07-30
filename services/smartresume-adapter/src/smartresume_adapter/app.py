"""FastAPI application for the SmartResume Adapter.

Delivers an achievement or credential payload to a learner's SmartResume record.
The Delivery Router owns the outer delivery-action envelope; this service owns
only the adapter-specific contract in ``schemas.py`` (design §2). SmartResume
errors are normalized into a ``status: "failed"`` response (200) rather than
propagated as HTTP errors, so the router always gets the adapter contract back.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI

from smartresume_adapter import delivery, resultmap
from smartresume_adapter.config import Settings, get_settings
from smartresume_adapter.schemas import DeliverRequest, DeliverResponse

logger = logging.getLogger("smartresume_adapter")


def create_app(settings: Settings | None = None, client: httpx.Client | None = None) -> FastAPI:
    settings = settings or get_settings()
    client = client or httpx.Client()
    app = FastAPI(
        title="SmartResume Adapter",
        version="0.1.0",
        summary="Deliver an achievement or credential to a SmartResume record (POC)",
    )
    app.state.settings = settings
    app.state.client = client

    @app.post("/internal/deliver-to-smartresume")
    def deliver_to_smartresume(req: DeliverRequest) -> DeliverResponse:
        try:
            resp = delivery.deliver(
                client,
                settings.api_url,
                settings.client_id,
                settings.access_key,
                req.payload,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "smartresume delivery failed workflow_id=%s execution_id=%s step_id=%s "
                "correlation_id=%s: %s",
                req.workflow_id,
                req.execution_id,
                req.step_id,
                req.correlation_id,
                exc,
            )
            return resultmap.to_error(req, str(exc))
        result = resultmap.to_result(req, resp)
        logger.info(
            "smartresume delivery %s workflow_id=%s execution_id=%s step_id=%s "
            "correlation_id=%s ref=%s",
            result.status,
            req.workflow_id,
            req.execution_id,
            req.step_id,
            req.correlation_id,
            result.external_reference_id,
        )
        return result

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so the adapter's INFO logs are emitted (uvicorn
    # doesn't do this for app loggers). Level via SMARTRESUME_ADAPTER_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
