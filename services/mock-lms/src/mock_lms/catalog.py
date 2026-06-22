"""Mock LMS data model, in-memory store, and fixture loader.

The store holds a single, fixed **catalog** of Canvas-style entities — courses,
users, outcomes, assignments, submissions, rubrics, badges — plus the
**Actions** each course offers. An Action is "grade an assignment"; the event it
emits is derived from the course kind and the graded assignment's role (see
``mock_lms.events``). Entities are indexed by id (Canvas ids are global), so the
LMS Resource APIs resolve an id regardless of which course references it.

The catalog is assembled offline (real roster CSV subset + generated
academic/credential layer), captured to a committed fixture, and loaded
read-only at runtime (design §3; requirements §5.3 FR-A1).
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from importlib.resources import files
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Single demo root account. Carried in event ``metadata.root_account_id`` and is
# the account the Context Builder's user-by-UUID lookup runs against.
ROOT_ACCOUNT_ID = "1"

# --- Enums ------------------------------------------------------------------


class CourseKind(StrEnum):
    """Whether a course can issue digital credentials (design §2 matrix)."""

    STANDARD = "standard"
    DIGITAL_CREDENTIAL = "digital_credential"


class AssignmentRole(StrEnum):
    """A module-level assignment vs the course's final assignment."""

    MODULE = "module"
    FINAL = "final"


# --- Canvas-style entities (minimal fields the Context Builder consumes) ----


class Course(BaseModel):
    id: str
    name: str
    course_code: str
    kind: CourseKind = CourseKind.STANDARD
    institution: str = ""
    term: str = ""
    workflow_state: str = "available"


class User(BaseModel):
    id: str
    # Canvas user UUID — carried in skill_mastered events; the Context Builder
    # resolves it back to ``id`` via the account-users lookup.
    uuid: str = ""
    name: str
    sortable_name: str
    login_id: str
    # Badge recipient identity (design §3).
    email: str
    # Canvas SIS ``property:*`` columns carried through for flavor.
    profile: dict[str, str] = {}


class Enrollment(BaseModel):
    id: str
    course_id: str
    user_id: str
    type: str = "StudentEnrollment"
    enrollment_state: str = "active"
    # Final course grade (design §3): drives course_completed pass/fail.
    current_grade: str | None = None
    current_points: float | None = None


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
    id: str = ""
    course_id: str
    url: str
    title: str
    body: str = ""


class Outcome(BaseModel):
    id: str
    title: str
    display_name: str = ""
    description: str = ""
    # Flat Canvas outcome code following the title convention: "N.0.0" is a
    # competency (e.g. "1.0.0"); "N.M.0" with a non-zero second segment is a
    # sub-competency (e.g. "1.2.0"). The title is prefixed with this code, so
    # competency-vs-sub is read from the convention rather than a separate flag.
    code: str = ""
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


class Assignment(BaseModel):
    id: str
    course_id: str
    name: str
    description: str = ""
    points_possible: float = 100.0
    due_at: datetime | None = None
    role: AssignmentRole = AssignmentRole.MODULE
    module_id: str | None = None
    # What grading this assignment is "about": an outcome (standard courses) or
    # a badge (digital-credential courses). Drives the emitted event body.
    outcome_id: str | None = None
    badge_id: str | None = None
    # Present when a rubric is associated; the Context Builder fetches the rubric
    # by this id (skill_mastered profile). The Mock LMS uses the rubric_id form
    # consistently (it does not embed the rubric schema on the assignment).
    rubric_id: str | None = None


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


class RubricRating(BaseModel):
    description: str
    points: float


class RubricCriterion(BaseModel):
    id: str
    description: str
    points: float
    ratings: list[RubricRating] = []


class Rubric(BaseModel):
    id: str
    course_id: str
    assignment_id: str | None = None
    title: str
    criteria: list[RubricCriterion] = []


class Badge(BaseModel):
    id: str
    course_id: str
    name: str
    description: str = ""
    outcome_id: str | None = None
    criteria: str = ""
    image_url: str | None = None
    # Acceptance gate (design §2): unaccepted badges are not fetchable, so
    # GET badge by id errors and the planner should decline to deliver.
    accepted: bool = True


class Action(BaseModel):
    """A grading Action a course offers; emits an event when run.

    The event type is derived (``mock_lms.events.action_event_type``) from the
    course kind and the graded assignment's role; the variant (happy/edge) falls
    out of the seed data the Action references (which outcome/badge, and the
    target learner's grade).
    """

    id: str
    course_id: str
    label: str
    assignment_id: str


class Catalog(BaseModel):
    courses: list[Course] = []
    users: list[User] = []
    enrollments: list[Enrollment] = []
    modules: list[Module] = []
    pages: list[Page] = []
    assignments: list[Assignment] = []
    outcomes: list[Outcome] = []
    outcome_results: list[OutcomeResult] = []
    outcome_alignments: list[OutcomeAlignment] = []
    submissions: list[Submission] = []
    rubrics: list[Rubric] = []
    badges: list[Badge] = []
    actions: list[Action] = []


# --- Store ------------------------------------------------------------------


class CatalogStore:
    def __init__(self, catalog: Catalog):
        self.courses = {c.id: c for c in catalog.courses}
        self.users = {u.id: u for u in catalog.users}
        self.outcomes = {o.id: o for o in catalog.outcomes}
        self.assignments = {a.id: a for a in catalog.assignments}
        self.badges = {b.id: b for b in catalog.badges}
        self.rubrics_by_id = {r.id: r for r in catalog.rubrics}
        self.users_by_uuid = {u.uuid: u for u in catalog.users if u.uuid}
        self._enrollments = list(catalog.enrollments)
        self._modules = list(catalog.modules)
        self._pages = list(catalog.pages)
        self._outcome_results = list(catalog.outcome_results)
        self._outcome_alignments = list(catalog.outcome_alignments)
        self._submissions = list(catalog.submissions)
        self._rubrics = list(catalog.rubrics)
        self._actions = list(catalog.actions)

    # Single-entity lookups (None if absent).
    def get_course(self, course_id: str) -> Course | None:
        return self.courses.get(course_id)

    def get_outcome(self, outcome_id: str) -> Outcome | None:
        return self.outcomes.get(outcome_id)

    def get_assignment(self, assignment_id: str) -> Assignment | None:
        return self.assignments.get(assignment_id)

    def get_user(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def get_badge(self, badge_id: str) -> Badge | None:
        return self.badges.get(badge_id)

    def get_action(self, action_id: str) -> Action | None:
        for a in self._actions:
            if a.id == action_id:
                return a
        return None

    def get_page(self, course_id: str, page_id: str) -> Page | None:
        for p in self._pages:
            if p.course_id == course_id and p.id == page_id:
                return p
        return None

    def get_rubric(self, rubric_id: str) -> Rubric | None:
        return self.rubrics_by_id.get(rubric_id)

    def users_for_uuids(self, uuids: list[str]) -> list[User]:
        return [u for uid in uuids if (u := self.users_by_uuid.get(uid)) is not None]

    # Collection lookups (filtered, Canvas-style).
    def enrollments(self, course_id: str, user_id: str | None = None) -> list[Enrollment]:
        return [
            e
            for e in self._enrollments
            if e.course_id == course_id and (user_id is None or e.user_id == user_id)
        ]

    def enrollment(self, course_id: str, user_id: str) -> Enrollment | None:
        for e in self._enrollments:
            if e.course_id == course_id and e.user_id == user_id:
                return e
        return None

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

    def outcome_result(
        self, course_id: str, user_id: str, outcome_id: str
    ) -> OutcomeResult | None:
        for r in self._outcome_results:
            if r.course_id == course_id and r.user_id == user_id and r.outcome_id == outcome_id:
                return r
        return None

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

    def submission(
        self, course_id: str, assignment_id: str, user_id: str
    ) -> Submission | None:
        for s in self._submissions:
            if (
                s.course_id == course_id
                and s.assignment_id == assignment_id
                and s.user_id == user_id
            ):
                return s
        return None

    def rubrics(self, course_id: str) -> list[Rubric]:
        return [r for r in self._rubrics if r.course_id == course_id]

    def actions_for(self, course_id: str) -> list[Action]:
        return [a for a in self._actions if a.course_id == course_id]


# --- Fixture loading --------------------------------------------------------


def _read_fixture(name: str, fixtures_dir: str | None = None) -> Any:
    if fixtures_dir is not None:
        raw = (Path(fixtures_dir) / name).read_text(encoding="utf-8")
    else:
        raw = (files("mock_lms.fixtures") / name).read_text(encoding="utf-8")
    return json.loads(raw)


def load_catalog(fixtures_dir: str | None = None) -> CatalogStore:
    """Build the store from a captured fixture snapshot.

    Defaults to the packaged (committed) canonical fixture; pass ``fixtures_dir``
    to load a generated set from the filesystem instead.
    """
    catalog = Catalog.model_validate(_read_fixture("catalog.json", fixtures_dir))
    return CatalogStore(catalog=catalog)
