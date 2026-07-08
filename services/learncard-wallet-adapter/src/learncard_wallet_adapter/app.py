"""FastAPI application for the LearnCard Wallet Adapter.

Delivers an already-issued credential into a LearnCard wallet. The Delivery
Router owns the outer delivery-action envelope; this service owns only the
adapter-specific contract in ``schemas.py`` (design §2). LearnCard errors are
normalized into a ``status: "failed"`` response (200) rather than propagated as
HTTP errors, so the router always gets the adapter contract back.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import FastAPI
from learncard_api import LearnCardClient, LearnCardSettings

from learncard_wallet_adapter import delivery, resultmap
from learncard_wallet_adapter.config import Settings, get_settings
from learncard_wallet_adapter.schemas import DeliverRequest, DeliverResponse

logger = logging.getLogger("learncard_wallet_adapter")


def create_app(
    settings: Settings | None = None, client: LearnCardClient | None = None
) -> FastAPI:
    settings = settings or get_settings()
    client = client or LearnCardClient(LearnCardSettings())
    app = FastAPI(
        title="LearnCard Wallet Adapter",
        version="0.1.0",
        summary="Deliver an already-issued credential to a LearnCard wallet (POC)",
    )
    app.state.settings = settings
    app.state.client = client

    @app.post("/internal/deliver-to-learncard-wallet")
    def deliver_to_wallet(req: DeliverRequest) -> DeliverResponse:
        try:
            uri = delivery.deliver(
                client, req.payload.recipient_profile_id, req.payload.signed_credential
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "wallet delivery failed workflow_id=%s execution_id=%s step_id=%s "
                "correlation_id=%s: %s",
                req.workflow_id,
                req.execution_id,
                req.step_id,
                req.correlation_id,
                exc,
            )
            return resultmap.to_error(req, str(exc))
        logger.info(
            "wallet delivery accepted workflow_id=%s execution_id=%s step_id=%s "
            "correlation_id=%s ref=%s",
            req.workflow_id,
            req.execution_id,
            req.step_id,
            req.correlation_id,
            uri,
        )
        return resultmap.to_success(req, uri)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so the adapter's INFO logs are emitted (uvicorn
    # doesn't do this for app loggers). Level via LEARNCARD_WALLET_ADAPTER_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
