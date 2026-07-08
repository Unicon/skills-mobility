"""FastAPI application for the LearnCard Profile Resolver.

Invoked by the Orchestrator (not via the Delivery Router) as a step before any
LearnCard issuance or delivery. Resolves a learner identifier to a LearnCard
profile via the mapping store then Search Profiles; LearnCard/transport errors
are normalized to a ``status: "failed"`` response (200) rather than propagated.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import FastAPI
from learncard_api import LearnCardClient, LearnCardSettings

from learncard_profile_resolver import resolver, resultmap
from learncard_profile_resolver.config import Settings, get_settings
from learncard_profile_resolver.schemas import ResolveRequest, ResolveResponse
from learncard_profile_resolver.store import SqliteMappingStore

logger = logging.getLogger("learncard_profile_resolver")


def create_app(
    settings: Settings | None = None, client: LearnCardClient | None = None
) -> FastAPI:
    settings = settings or get_settings()
    client = client or LearnCardClient(LearnCardSettings())
    store = SqliteMappingStore(settings.db_path)
    app = FastAPI(
        title="LearnCard Profile Resolver",
        version="0.1.0",
        summary="Resolve a learner identifier to a LearnCard profile (POC)",
    )
    app.state.settings = settings
    app.state.store = store
    app.state.client = client

    @app.post("/resolve-learncard-profile")
    def resolve_profile(req: ResolveRequest) -> ResolveResponse:
        # Correlation ids preserved in logs and the result record (FR-LPR-11).
        ids = {
            "workflow_id": req.workflow_id,
            "execution_id": req.execution_id,
            "step_id": req.step_id,
            "correlation_id": req.correlation_id,
        }
        try:
            resp = resolver.resolve(req.payload, store, client)
        except httpx.HTTPError as exc:
            logger.warning(
                "resolution failed workflow_id=%s execution_id=%s step_id=%s "
                "correlation_id=%s: %s",
                req.workflow_id,
                req.execution_id,
                req.step_id,
                req.correlation_id,
                exc,
            )
            return resultmap.error(str(exc)).model_copy(update=ids)
        logger.info(
            "resolution workflow_id=%s execution_id=%s step_id=%s correlation_id=%s status=%s",
            req.workflow_id,
            req.execution_id,
            req.step_id,
            req.correlation_id,
            resp.status,
        )
        return resp.model_copy(update=ids)

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app


def run() -> None:
    import uvicorn

    settings = get_settings()
    # Configure the root logger so the resolver's INFO logs are emitted (uvicorn
    # doesn't do this for app loggers). Level via LEARNCARD_PROFILE_RESOLVER_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
