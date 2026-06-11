"""Emission control endpoints (UI-facing): trigger events, run scenarios, inspect log."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from skills_mobility_events import new_correlation_id, new_emission_id

from mock_lms.api import get_emission_log, get_emitter, get_store
from mock_lms.auth import Role, get_current_role
from mock_lms.builders import EventBuildError, build_envelope
from mock_lms.config import Settings, get_settings
from mock_lms.emission import EmissionLog, EmissionRecord, Emitter
from mock_lms.scenarios import EventSpec, ScenarioStore

router = APIRouter(prefix="/demo", tags=["emission"])

StoreDep = Annotated[ScenarioStore, Depends(get_store)]
EmitterDep = Annotated[Emitter, Depends(get_emitter)]
LogDep = Annotated[EmissionLog, Depends(get_emission_log)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RoleDep = Annotated[Role, Depends(get_current_role)]


class EmitRequest(BaseModel):
    event_type: str
    course_id: str
    user_id: str
    outcome_id: str | None = None
    assignment_id: str | None = None
    badge_id: str | None = None
    badge_name: str | None = None
    credential_type: str | None = None


def _emit_spec(
    spec: EventSpec,
    *,
    store: ScenarioStore,
    emitter: Emitter,
    log: EmissionLog,
    settings: Settings,
    correlation_id: str,
    scenario_id: str | None,
) -> dict[str, Any]:
    try:
        envelope = build_envelope(
            store,
            spec,
            correlation_id=correlation_id,
            scenario_id=scenario_id,
            root_account_uuid=settings.root_account_uuid,
        )
    except EventBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    emitter.emit(envelope)
    record = EmissionRecord(
        emission_id=new_emission_id(),
        correlation_id=correlation_id,
        scenario_id=scenario_id,
        event_type=spec.event_type,
        event_name=envelope.metadata.event_name,
        event_time=envelope.metadata.event_time,
        target=emitter.target,
        envelope=envelope.model_dump(mode="json"),
    )
    log.append(record)
    return {"emission_id": record.emission_id, "envelope": record.envelope}


@router.post("/emit")
def emit_event(
    payload: EmitRequest,
    store: StoreDep,
    emitter: EmitterDep,
    log: LogDep,
    settings: SettingsDep,
    role: RoleDep,
) -> dict[str, Any]:
    correlation_id = new_correlation_id()
    spec = EventSpec(**payload.model_dump())
    result = _emit_spec(
        spec,
        store=store,
        emitter=emitter,
        log=log,
        settings=settings,
        correlation_id=correlation_id,
        scenario_id=None,
    )
    return {"correlation_id": correlation_id, **result}


@router.get("/scenarios")
def list_scenarios(store: StoreDep) -> list[dict[str, Any]]:
    return [
        {
            "id": s.id,
            "title": s.title,
            "description": s.description,
            "event_count": len(s.events),
            # Events let the UI inspect exactly the context a scenario will emit.
            "events": [e.model_dump(mode="json") for e in s.events],
        }
        for s in store.scenarios.values()
    ]


@router.post("/scenarios/{scenario_id}/run")
def run_scenario(
    scenario_id: str,
    store: StoreDep,
    emitter: EmitterDep,
    log: LogDep,
    settings: SettingsDep,
    role: RoleDep,
) -> dict[str, Any]:
    scenario = store.scenarios.get(scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail=f"scenario {scenario_id} not found")
    correlation_id = new_correlation_id()
    emissions = [
        _emit_spec(
            spec,
            store=store,
            emitter=emitter,
            log=log,
            settings=settings,
            correlation_id=correlation_id,
            scenario_id=scenario_id,
        )
        for spec in scenario.events
    ]
    return {"run_id": correlation_id, "correlation_id": correlation_id, "emissions": emissions}


@router.post("/scenarios/{scenario_id}/reset")
def reset(scenario_id: str, store: StoreDep, log: LogDep, role: RoleDep) -> dict[str, Any]:
    if scenario_id not in store.scenarios:
        raise HTTPException(status_code=404, detail=f"scenario {scenario_id} not found")
    # Seed data is read-only; reset clears the emission log so a re-run starts clean.
    log.clear()
    return {"ok": True, "scenario_id": scenario_id}


@router.get("/emissions")
def list_emissions(log: LogDep, since: int = 0) -> dict[str, Any]:
    return {
        "cursor": log.cursor,
        "emissions": [r.to_public_dict() for r in log.since(since)],
    }
