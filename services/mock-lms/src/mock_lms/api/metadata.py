"""Canvas-style read endpoints (the "LMS Metadata APIs").

Paths and query shapes mirror Canvas so the Context Builder integration is
realistic; only the fields the Context Builder consumes are populated. Responses
are deterministic per the seeded catalog (requirements §5.3). Unknown ids return
Canvas-style 404 envelopes.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from mock_lms.api import get_store
from mock_lms.scenarios import ScenarioStore

router = APIRouter(prefix="/api/v1", tags=["lms-metadata"])

StoreDep = Annotated[ScenarioStore, Depends(get_store)]


def _not_found(message: str) -> HTTPException:
    # Canvas returns {"errors": [{"message": ...}]} on 404.
    return HTTPException(status_code=404, detail={"errors": [{"message": message}]})


@router.get("/courses/{course_id}")
def get_course(course_id: str, store: StoreDep) -> dict[str, Any]:
    course = store.get_course(course_id)
    if course is None:
        raise _not_found(f"course {course_id} not found")
    return course.model_dump(mode="json")


@router.get("/courses/{course_id}/enrollments")
def get_enrollments(
    course_id: str,
    store: StoreDep,
    user_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    return [e.model_dump(mode="json") for e in store.enrollments(course_id, user_id)]


@router.get("/courses/{course_id}/modules")
def get_modules(
    course_id: str,
    store: StoreDep,
    include: Annotated[list[str] | None, Query(alias="include[]")] = None,
) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    want_items = include is not None and "items" in include
    out = []
    for m in store.modules(course_id):
        dumped = m.model_dump(mode="json")
        if not want_items:
            dumped.pop("items", None)
        out.append(dumped)
    return out


@router.get("/courses/{course_id}/pages")
def get_pages(course_id: str, store: StoreDep) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    return [p.model_dump(mode="json") for p in store.pages(course_id)]


@router.get("/courses/{course_id}/pages/{url}")
def get_page(course_id: str, url: str, store: StoreDep) -> dict[str, Any]:
    page = store.get_page(course_id, url)
    if page is None:
        raise _not_found(f"page {url} not found in course {course_id}")
    return page.model_dump(mode="json")


@router.get("/courses/{course_id}/assignments")
def get_assignments(course_id: str, store: StoreDep) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    return [a.model_dump(mode="json") for a in store.assignments_for(course_id)]


@router.get("/outcomes/{outcome_id}")
def get_outcome(outcome_id: str, store: StoreDep) -> dict[str, Any]:
    outcome = store.get_outcome(outcome_id)
    if outcome is None:
        raise _not_found(f"outcome {outcome_id} not found")
    return outcome.model_dump(mode="json")


@router.get("/courses/{course_id}/outcome_results")
def get_outcome_results(
    course_id: str,
    store: StoreDep,
    user_ids: Annotated[list[str] | None, Query(alias="user_ids[]")] = None,
    outcome_ids: Annotated[list[str] | None, Query(alias="outcome_ids[]")] = None,
    include: Annotated[list[str] | None, Query(alias="include[]")] = None,
) -> dict[str, Any]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    results = store.outcome_results(course_id, user_ids=user_ids, outcome_ids=outcome_ids)
    payload: dict[str, Any] = {"outcome_results": [r.model_dump(mode="json") for r in results]}
    if include and "alignments" in include:
        payload["linked"] = {
            "alignments": [a.model_dump(mode="json") for a in store.outcome_alignments(course_id)]
        }
    return payload


@router.get("/courses/{course_id}/outcome_alignments")
def get_outcome_alignments(
    course_id: str,
    store: StoreDep,
    student_id: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    return [a.model_dump(mode="json") for a in store.outcome_alignments(course_id)]


@router.get("/courses/{course_id}/students/submissions")
def get_submissions(
    course_id: str,
    store: StoreDep,
    student_ids: Annotated[list[str] | None, Query(alias="student_ids[]")] = None,
    assignment_ids: Annotated[list[str] | None, Query(alias="assignment_ids[]")] = None,
) -> list[dict[str, Any]]:
    if store.get_course(course_id) is None:
        raise _not_found(f"course {course_id} not found")
    subs = store.submissions(course_id, student_ids=student_ids, assignment_ids=assignment_ids)
    return [s.model_dump(mode="json") for s in subs]
