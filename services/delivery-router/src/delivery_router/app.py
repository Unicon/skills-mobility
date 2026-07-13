"""FastAPI application for the Delivery Router.

One request = one delivery action. Validates the envelope, dispatches to the
configured adapter, and returns a normalized result. Transport failures (after
config-driven retries) are normalized to ``status: "failed"`` (HTTP 200) so the
Orchestrator always gets the router contract back. Emits standardized
delivery-attempt / delivery-result log lines (the Orchestrator owns the
persisted correlated execution view, per ADR-0016).
"""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI

from delivery_router import dispatcher
from delivery_router.clients import AdapterClient
from delivery_router.config import Settings, get_settings
from delivery_router.schemas import DeliveryActionRequest, DeliveryActionResponse

logger = logging.getLogger("delivery_router")


def create_app(settings: Settings | None = None, client: AdapterClient | None = None) -> FastAPI:
    settings = settings or get_settings()
    client = client or AdapterClient(
        timeout=settings.request_timeout, retry_limit=settings.retry_limit
    )
    app = FastAPI(
        title="Delivery Router",
        version="0.1.0",
        summary="Dispatch approved delivery actions to target adapters (POC)",
    )
    app.state.settings = settings
    app.state.client = client

    @app.post("/delivery-actions")
    def delivery_actions(req: DeliveryActionRequest) -> DeliveryActionResponse:
        # All four correlation identifiers on every delivery log line (FR-DR-5).
        logger.info(
            "delivery attempt action=%s workflow_id=%s execution_id=%s step_id=%s "
            "correlation_id=%s",
            req.action.value,
            req.workflow_id,
            req.execution_id,
            req.step_id,
            req.correlation_id,
        )
        try:
            resp = dispatcher.dispatch(req, settings, client)
        except httpx.HTTPError as exc:
            logger.warning(
                "delivery dispatch failed action=%s workflow_id=%s execution_id=%s step_id=%s "
                "correlation_id=%s: %s",
                req.action.value,
                req.workflow_id,
                req.execution_id,
                req.step_id,
                req.correlation_id,
                exc,
            )
            return DeliveryActionResponse(
                status="failed",
                adapter_key=req.adapter_key,
                action=req.action,
                error={"message": str(exc)},
            )
        logger.info(
            "delivery result action=%s workflow_id=%s execution_id=%s step_id=%s "
            "correlation_id=%s status=%s ref=%s",
            req.action.value,
            req.workflow_id,
            req.execution_id,
            req.step_id,
            req.correlation_id,
            resp.status,
            resp.external_reference_id,
        )
        return resp

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so the router's INFO logs are emitted (uvicorn
    # doesn't do this for app loggers). Level via DELIVERY_ROUTER_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
