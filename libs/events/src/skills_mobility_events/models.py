"""Event contracts for the Skills Mobility POC.

The Mock Event Producer is the source of truth for these schemas. Emitted
events use a Canvas Live Events-style ``{ metadata, body }`` envelope; the
``metadata`` adds two POC traceability fields (``correlation_id`` and
``action_id``) on top of the Canvas-standard fields. Those additions are
additive and ignored by anything expecting a vanilla Canvas event.

See: docs/2_requirements/mock-lms-event-producer.md §4 and
docs/3_design/mock-lms.md §2.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EventType(StrEnum):
    """Business event types owned by the producer (the POC happy paths)."""

    SKILL_MASTERED = "skill_mastered"
    COURSE_COMPLETED = "course_completed"
    BADGE_AWARDED = "badge_awarded"


# Maps our business event type to the Canvas Live Events ``event_name`` it is
# modeled on. Where Canvas has no equivalent, we keep a POC-defined name.
CANVAS_EVENT_NAMES: dict[EventType, str] = {
    EventType.SKILL_MASTERED: "learning_outcome_result_created",
    EventType.COURSE_COMPLETED: "course_completed",
    EventType.BADGE_AWARDED: "badge_awarded",
}


def canvas_event_name(event_type: EventType) -> str:
    return CANVAS_EVENT_NAMES[event_type]


class EventMetadata(BaseModel):
    """Canvas Live Events-style metadata, plus POC traceability fields."""

    event_name: str
    event_time: datetime
    producer: str = "mock-lms"
    # Canvas carries both; the Context Builder's account-user lookup keys on the
    # id. user_id is always present (the Event Consumer's ingress idempotency and
    # FR-EC-9 require it on every event).
    root_account_id: str | None = None
    root_account_uuid: str | None = None
    user_id: str
    context_type: str | None = None
    context_id: str | None = None
    # Unique per emission.
    event_id: str
    # POC traceability extensions:
    correlation_id: str
    # Which catalog Action produced this event (stable business id).
    action_id: str | None = None


class LiveEventEnvelope(BaseModel):
    """The wire format for every emitted event."""

    metadata: EventMetadata
    body: dict[str, Any]


# --- Event-type body shapes -------------------------------------------------
# Modeled on Canvas live-event bodies where one exists; POC-defined otherwise.
# Builders construct these and serialize them into ``LiveEventEnvelope.body``.


class LearningOutcomeResultBody(BaseModel):
    """Body for ``skill_mastered`` (Canvas ``learning_outcome_result_created``).

    Canvas-shaped: the course and assignment are carried as ``*_context`` /
    ``associated_asset`` references, and the learner by ``user_uuid`` (the Canvas
    ``user_id`` is resolved downstream via the account-users lookup; it is also
    present in ``metadata.user_id``).
    """

    learning_outcome_result_id: str
    learning_outcome_id: str
    result_id: str | None = None
    score: float
    possible: float
    mastery: bool
    title: str | None = None
    result_context_type: str = "Course"
    result_context_id: str
    associated_asset_type: str = "Assignment"
    associated_asset_id: str
    user_uuid: str
    submitted_or_assessed_at: datetime | None = None


class CourseRef(BaseModel):
    """Nested course reference (Canvas nests the course object in this body)."""

    id: str
    name: str | None = None


class CourseCompletedBody(BaseModel):
    """Body for ``course_completed`` (Canvas ``course_completed``)."""

    course: CourseRef
    completed_at: datetime
    progress_percent: float = 100.0
    # Final course grade/score. Whether that's passing or failing is a downstream
    # judgment (a grading-policy concern), not baked into the event as a boolean.
    final_grade: str | None = None
    final_score: float | None = None


class BadgeAwardedBody(BaseModel):
    """Body for ``badge_awarded`` (POC-defined)."""

    badge_id: str
    badge_name: str
    user_id: str
    course_id: str
    outcome_id: str | None = None
    awarded_at: datetime
    criteria: str | None = None
    # Acceptance is deliberately NOT on the event: as in the real world, a
    # consumer learns it by fetching the badge (GET badge by id), which errors
    # for an unaccepted badge. The planner's acceptance gate keys off that read.


BodyModel = LearningOutcomeResultBody | CourseCompletedBody | BadgeAwardedBody

__all__ = [
    "EventType",
    "CANVAS_EVENT_NAMES",
    "canvas_event_name",
    "EventMetadata",
    "LiveEventEnvelope",
    "LearningOutcomeResultBody",
    "CourseRef",
    "CourseCompletedBody",
    "BadgeAwardedBody",
    "BodyModel",
]
