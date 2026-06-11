"""Mock LMS data model, in-memory store, and fixture loader.

The store holds a single, fixed **catalog** of Canvas-style entities (courses,
students, outcomes, assignments, submissions, ...) plus a set of named
**scenarios**. A scenario is a demo narrative: metadata + an ordered list of
events to emit. Entities are indexed by id (Canvas ids are global), so the
metadata APIs resolve an id regardless of which scenario references it.

Fixtures are version-controlled (they define the canonical demos); the store is
read-only at runtime (requirements §5.3 FR-A1).
"""

from __future__ import annotations

import json
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# --- Canvas-style entities (minimal fields the Context Builder consumes) ----


class Course(BaseModel):
    id: str
    name: str
    course_code: str
    workflow_state: str = "available"


class Student(BaseModel):
    id: str
    name: str
    sortable_name: str
    login_id: str


class Enrollment(BaseModel):
    id: str
    course_id: str
    user_id: str
    type: str = "StudentEnrollment"
    enrollment_state: str = "active"


class ModuleItem(BaseModel):
    id: str
    title: str
    type: str
    content_id: str | None = None


class Module(BaseModel):
    id: str
    course_id: str
    name: str
    position: int = 1
    items: list[ModuleItem] = []


class Page(BaseModel):
    course_id: str
    url: str
    title: str
    body: str = ""


class Assignment(BaseModel):
    id: str
    course_id: str
    name: str
    description: str = ""
    points_possible: float = 100.0
    due_at: datetime | None = None


class Outcome(BaseModel):
    id: str
    title: str
    display_name: str = ""
    description: str = ""
    mastery_points: float = 3.0
    points_possible: float = 5.0


class OutcomeResult(BaseModel):
    id: str
    course_id: str
    user_id: str
    outcome_id: str
    assignment_id: str | None = None
    score: float
    possible: float = 5.0
    mastery: bool = False
    submitted_or_assessed_at: datetime | None = None


class OutcomeAlignment(BaseModel):
    id: str
    course_id: str
    outcome_id: str
    assignment_id: str
    name: str


class Submission(BaseModel):
    id: str
    course_id: str
    assignment_id: str
    user_id: str
    score: float | None = None
    grade: str | None = None
    workflow_state: str = "graded"
    submitted_at: datetime | None = None
    graded_at: datetime | None = None


class Catalog(BaseModel):
    courses: list[Course] = []
    students: list[Student] = []
    enrollments: list[Enrollment] = []
    modules: list[Module] = []
    pages: list[Page] = []
    assignments: list[Assignment] = []
    outcomes: list[Outcome] = []
    outcome_results: list[OutcomeResult] = []
    outcome_alignments: list[OutcomeAlignment] = []
    submissions: list[Submission] = []


class EventSpec(BaseModel):
    """One event in a scenario's emission script."""

    event_type: str
    user_id: str
    course_id: str
    outcome_id: str | None = None
    assignment_id: str | None = None
    badge_id: str | None = None
    badge_name: str | None = None
    credential_type: str | None = None
    delay_ms: int = 0


class Scenario(BaseModel):
    id: str
    title: str
    description: str = ""
    events: list[EventSpec] = []


# --- Store ------------------------------------------------------------------


class ScenarioStore:
    def __init__(self, catalog: Catalog, scenarios: list[Scenario]):
        self.courses = {c.id: c for c in catalog.courses}
        self.students = {s.id: s for s in catalog.students}
        self.outcomes = {o.id: o for o in catalog.outcomes}
        self.assignments = {a.id: a for a in catalog.assignments}
        self._enrollments = list(catalog.enrollments)
        self._modules = list(catalog.modules)
        self._pages = list(catalog.pages)
        self._outcome_results = list(catalog.outcome_results)
        self._outcome_alignments = list(catalog.outcome_alignments)
        self._submissions = list(catalog.submissions)
        self.scenarios = {s.id: s for s in scenarios}

    # Single-entity lookups (None if absent).
    def get_course(self, course_id: str) -> Course | None:
        return self.courses.get(course_id)

    def get_outcome(self, outcome_id: str) -> Outcome | None:
        return self.outcomes.get(outcome_id)

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        return self.assignments.get(assignment_id)

    def get_student(self, user_id: str) -> Student | None:
        return self.students.get(user_id)

    def get_page(self, course_id: str, url: str) -> Page | None:
        for p in self._pages:
            if p.course_id == course_id and p.url == url:
                return p
        return None

    # Collection lookups (filtered, Canvas-style).
    def enrollments(self, course_id: str, user_id: str | None = None) -> list[Enrollment]:
        return [
            e
            for e in self._enrollments
            if e.course_id == course_id and (user_id is None or e.user_id == user_id)
        ]

    def modules(self, course_id: str) -> list[Module]:
        return [m for m in self._modules if m.course_id == course_id]

    def pages(self, course_id: str) -> list[Page]:
        return [p for p in self._pages if p.course_id == course_id]

    def assignments_for(self, course_id: str) -> list[Assignment]:
        return [a for a in self.assignments.values() if a.course_id == course_id]

    def outcome_results(
        self,
        course_id: str,
        user_ids: list[str] | None = None,
        outcome_ids: list[str] | None = None,
    ) -> list[OutcomeResult]:
        return [
            r
            for r in self._outcome_results
            if r.course_id == course_id
            and (not user_ids or r.user_id in user_ids)
            and (not outcome_ids or r.outcome_id in outcome_ids)
        ]

    def outcome_alignments(self, course_id: str) -> list[OutcomeAlignment]:
        return [a for a in self._outcome_alignments if a.course_id == course_id]

    def submissions(
        self,
        course_id: str,
        student_ids: list[str] | None = None,
        assignment_ids: list[str] | None = None,
    ) -> list[Submission]:
        return [
            s
            for s in self._submissions
            if s.course_id == course_id
            and (not student_ids or s.user_id in student_ids)
            and (not assignment_ids or s.assignment_id in assignment_ids)
        ]


# --- Fixture loading --------------------------------------------------------


def _read_fixture(name: str, fixtures_dir: str | None = None) -> Any:
    if fixtures_dir is not None:
        raw = (Path(fixtures_dir) / name).read_text(encoding="utf-8")
    else:
        raw = (files("mock_lms.fixtures") / name).read_text(encoding="utf-8")
    return json.loads(raw)


def load_store(fixtures_dir: str | None = None) -> ScenarioStore:
    """Build the store from a captured fixture snapshot.

    Defaults to the packaged (committed) canonical fixtures; pass ``fixtures_dir``
    to load a generated set from the filesystem instead.
    """
    catalog = Catalog.model_validate(_read_fixture("catalog.json", fixtures_dir))
    scenarios = [Scenario.model_validate(s) for s in _read_fixture("scenarios.json", fixtures_dir)]
    return ScenarioStore(catalog=catalog, scenarios=scenarios)
