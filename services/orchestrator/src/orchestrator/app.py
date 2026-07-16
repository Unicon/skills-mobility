"""FastAPI application factory for the Orchestrator.

`POST /run-workflow` runs the planner + executor paths and persists the trail;
`GET /executions` lists recent executions (optionally filtered by `correlation_id`)
and `GET /executions/{id}` returns the correlated execution metadata.
`PUT /admin/plan-lookup-toggle` enables/disables reusable delivery-phase plan
lookup (FR-OR-28) and `DELETE /admin/plans/{id}` forces regeneration (FR-OR-29).
Seams default to the Phase-1 stubs.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from orchestrator import engine
from orchestrator.clients import (
    ContextBuilderClient,
    DeliveryRouterClient,
    DeliveryTargetsClient,
    FieldMappingClient,
    HttpContextBuilderClient,
    HttpDeliveryRouterClient,
    HttpDeliveryTargetsClient,
    HttpFieldMappingClient,
    HttpProfileResolverClient,
    HttpWorkflowActionsClient,
    ProfileResolverClient,
    StubContextBuilder,
    StubDeliveryRouter,
    StubFieldMapping,
    StubProfileResolver,
    WorkflowActionsClient,
)
from orchestrator.config import Settings, get_settings
from orchestrator.schemas import WorkflowStartRequest
from orchestrator.store import ExecutionStore


class PlanLookupToggle(BaseModel):
    enabled: bool


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="Orchestrator",
        version="0.1.0",
        summary="Phase-1 constrained plan executor (POC)",
    )
    app.state.settings = settings
    app.state.store = ExecutionStore(settings.db_path)
    # Context Builder is built (#20): use the real HTTP client when its URL is set.
    context_builder: ContextBuilderClient = (
        HttpContextBuilderClient(settings.context_builder_url)
        if settings.context_builder_url
        else StubContextBuilder()
    )
    app.state.context_builder = context_builder
    # Profile Resolver (#51) + Delivery Router (#56): real HTTP clients when their
    # URLs are set, else the Phase-1 in-process stubs.
    profile_resolver: ProfileResolverClient = (
        HttpProfileResolverClient(settings.profile_resolver_url)
        if settings.profile_resolver_url
        else StubProfileResolver()
    )
    delivery_router: DeliveryRouterClient = (
        HttpDeliveryRouterClient(settings.delivery_router_url)
        if settings.delivery_router_url
        else StubDeliveryRouter()
    )
    # Field Mapping (#27): real HTTP client when its URL is set, else the stub.
    field_mapping: FieldMappingClient = (
        HttpFieldMappingClient(settings.field_mapping_url)
        if settings.field_mapping_url
        else StubFieldMapping()
    )
    app.state.profile_resolver = profile_resolver
    app.state.delivery_router = delivery_router
    app.state.field_mapping = field_mapping
    # LLM Decision Service planner seams (#77/#78): real HTTP clients when their
    # URLs are set, else None → the engine uses the deterministic planner stubs.
    delivery_targets: DeliveryTargetsClient | None = (
        HttpDeliveryTargetsClient(settings.delivery_targets_url)
        if settings.delivery_targets_url
        else None
    )
    workflow_actions: WorkflowActionsClient | None = (
        HttpWorkflowActionsClient(settings.workflow_actions_url)
        if settings.workflow_actions_url
        else None
    )
    app.state.delivery_targets = delivery_targets
    app.state.workflow_actions = workflow_actions
    # Runtime-toggleable plan lookup (seeded from settings; FR-OR-28).
    app.state.reusable_plan_lookup_enabled = settings.reusable_plan_lookup_enabled

    @app.post("/run-workflow")
    def run_workflow(request: WorkflowStartRequest) -> dict[str, Any]:
        metadata = engine.run_workflow(
            request,
            store=app.state.store,
            context_builder=app.state.context_builder,
            profile_resolver=app.state.profile_resolver,
            delivery_router=app.state.delivery_router,
            field_mapping=app.state.field_mapping,
            issuer_id=settings.issuer_id,
            delivery_config_ref=settings.delivery_config_ref,
            recipient_profile_id=settings.demo_recipient_profile_id,
            delivery_targets=app.state.delivery_targets,
            workflow_actions=app.state.workflow_actions,
            reusable_plan_lookup=app.state.reusable_plan_lookup_enabled,
        )
        return metadata.model_dump()

    @app.get("/executions")
    def list_executions(
        limit: int = 50, correlation_id: str | None = None
    ) -> list[dict[str, Any]]:
        store: ExecutionStore = app.state.store
        rows = store.list_executions(limit=limit, correlation_id=correlation_id)
        return [r.model_dump() for r in rows]

    @app.get("/executions/{execution_id}")
    def get_execution(execution_id: str) -> dict[str, Any]:
        store: ExecutionStore = app.state.store
        metadata = store.get_execution_metadata(execution_id)
        if metadata is None:
            raise HTTPException(
                status_code=404,
                detail={"errors": [{"message": f"execution {execution_id} not found"}]},
            )
        return metadata.model_dump()

    @app.put("/admin/plan-lookup-toggle", tags=["admin"])
    def set_plan_lookup(toggle: PlanLookupToggle) -> dict[str, Any]:
        app.state.reusable_plan_lookup_enabled = toggle.enabled
        return {"reusable_plan_lookup_enabled": toggle.enabled}

    @app.delete("/admin/plans/{plan_id}", tags=["admin"])
    def delete_plan(plan_id: str) -> dict[str, Any]:
        store: ExecutionStore = app.state.store
        return {"deleted": store.delete_plan(plan_id)}

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, Any]:
        return {"status": "ok"}

    return app


def run() -> None:
    import logging

    import uvicorn

    settings = get_settings()
    # Configure the root logger so the engine/executor INFO logs are emitted
    # (uvicorn doesn't configure app loggers). Level via ORCHESTRATOR_LOG_LEVEL.
    logging.basicConfig(level=settings.log_level.upper())
    uvicorn.run(create_app(settings), host="127.0.0.1", port=settings.port)
