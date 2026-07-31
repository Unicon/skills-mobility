"""Emission control API (UI-facing): courses, their Actions, and running them.

The operator never emits raw events. A course offers grading **Actions**; running
one emits 1..N events (one learner, or one per enrolled learner) and returns the
emitted envelope(s) synchronously so the UI can show exactly what was emitted.
There is no live feed here — the persistent, cross-system view is the Admin UI's
(design §2/§4).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from skills_mobility_events import new_correlation_id

from mock_lms.api import get_emitter, get_store
from mock_lms.catalog import Action, CatalogStore, Course
from mock_lms.config import Settings, get_settings
from mock_lms.emitter import Emitter
from mock_lms.events import EventBuildError, action_event_type, build_envelope, resolve_targets

router = APIRouter(prefix="/demo", tags=["emission"])

StoreDep = Annotated[CatalogStore, Depends(get_store)]
EmitterDep = Annotated[Emitter, Depends(get_emitter)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


class RunActionRequest(BaseModel):
    action_id: str
    scope: str = "one"  # "one" | "all"
    user_id: str | None = None  # required-ish when scope == "one" (else first enrolled)


def _action_view(store: CatalogStore, course: Course, action: Action) -> dict[str, Any]:
    assignment = store.get_assignment(action.assignment_id)
    return {
        "id": action.id,
        "label": action.label,
        "assignment_id": action.assignment_id,
        "assignment_name": assignment.name if assignment else None,
        "event_type": action_event_type(course, assignment).value if assignment else None,
    }


@router.get("/courses")
def list_courses(store: StoreDep) -> list[dict[str, Any]]:
    """Courses + the Actions each offers (and the learners, for one-learner runs)."""
    out: list[dict[str, Any]] = []
    for course in store.courses.values():
        learners = [
            {"id": u.id, "name": u.name, "email": u.email}
            for e in store.enrollments(course.id)
            if (u := store.get_user(e.user_id)) is not None
        ]
        out.append(
            {
                **course.model_dump(mode="json"),
                "learners": learners,
                "actions": [_action_view(store, course, a) for a in store.actions_for(course.id)],
            }
        )
    return out


@router.post("/courses/{course_id}/actions")
def run_action(
    course_id: str,
    payload: RunActionRequest,
    store: StoreDep,
    emitter: EmitterDep,
    settings: SettingsDep,
) -> dict[str, Any]:
    course = store.get_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"course {course_id} not found")
    action = store.get_action(payload.action_id)
    if action is None or action.course_id != course_id:
        raise HTTPException(
            status_code=404, detail=f"action {payload.action_id} not found in course {course_id}"
        )

    correlation_id = new_correlation_id()
    try:
        targets = resolve_targets(store, action, payload.scope, payload.user_id)
        envelopes = [
            build_envelope(
                store,
                action,
                user,
                correlation_id=correlation_id,
                root_account_uuid=settings.root_account_uuid,
            )
            for user in targets
        ]
    except EventBuildError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    for envelope in envelopes:
        emitter.emit(envelope)

    return {
        "correlation_id": correlation_id,
        "action_id": action.id,
        "scope": payload.scope,
        "emitted": [e.model_dump(mode="json") for e in envelopes],
    }


@router.post("/reset")
def reset(emitter: EmitterDep) -> dict[str, Any]:
    """Clear emission state so a demo can re-run cleanly, and cascade the reset
    down the chain (Event Consumer → Orchestrator) so re-running a learner's
    events isn't blocked by ingress dedup. Seed data is read-only."""
    captured = getattr(emitter, "emitted", None)
    if captured is not None:
        captured.clear()
    return {"ok": True, "event_consumer": emitter.reset_downstream()}
