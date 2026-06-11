"""Event contracts for the Skills Mobility POC.

The Mock Event Producer is the source of truth for these schemas. Emitted
events use a Canvas Live Events-style ``{ metadata, body }`` envelope; the
``metadata`` adds two POC traceability fields (``correlation_id`` and
``scenario_id``) on top of the Canvas-standard fields. Those additions are
additive and ignored by anything expecting a vanilla Canvas event.

See: docs/2_requirements/mock-event-producer.md §5.2 and
docs/3_design/mock-event-producer.md §3.
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
    CREDENTIAL_ELIGIBLE = "credential_eligible"


# Maps our business event type to the Canvas Live Events ``event_name`` it is
# modeled on. Where Canvas has no equivalent, we keep a POC-defined name.
CANVAS_EVENT_NAMES: dict[EventType, str] = {
    EventType.SKILL_MASTERED: "learning_outcome_result_created",
    EventType.COURSE_COMPLETED: "course_completed",
    EventType.BADGE_AWARDED: "badge_awarded",
    EventType.CREDENTIAL_ELIGIBLE: "credential_eligible",
}


def canvas_event_name(event_type: EventType) -> str:
    return CANVAS_EVENT_NAMES[event_type]


class EventMetadata(BaseModel):
    """Canvas Live Events-style metadata, plus POC traceability fields."""

    event_name: str
    event_time: datetime
    producer: str = "mock-lms"
    root_account_uuid: str | None = None
    user_id: str | None = None
    context_type: str | None = None
    context_id: str | None = None
    # Unique per emission.
    event_id: str
    # POC traceability extensions:
    correlation_id: str
    scenario_id: str | None = None


class LiveEventEnvelope(BaseModel):
    """The wire format for every emitted event."""

    metadata: EventMetadata
    body: dict[str, Any]


# --- Event-type body shapes -------------------------------------------------
# Modeled on Canvas live-event bodies where one exists; POC-defined otherwise.
# Builders construct these and serialize them into ``LiveEventEnvelope.body``.


class LearningOutcomeResultBody(BaseModel):
    """Body for ``skill_mastered`` (Canvas ``learning_outcome_result_created``)."""

    learning_outcome_result_id: str
    learning_outcome_id: str
    user_id: str
    course_id: str
    result_id: str | None = None
    score: float
    possible: float
    mastery: bool
    title: str | None = None
    assignment_id: str | None = None
    submitted_or_assessed_at: datetime | None = None


class CourseCompletedBody(BaseModel):
    """Body for ``course_completed`` (Canvas ``course_completed``)."""

    course_id: str
    user_id: str
    completed_at: datetime
    progress_percent: float = 100.0


class BadgeAwardedBody(BaseModel):
    """Body for ``badge_awarded`` (POC-defined)."""

    badge_id: str
    badge_name: str
    user_id: str
    course_id: str
    outcome_id: str | None = None
    awarded_at: datetime
    criteria: str | None = None


class CredentialEligibleBody(BaseModel):
    """Body for ``credential_eligible`` (POC-defined)."""

    user_id: str
    course_id: str
    credential_type: str
    reason: str | None = None
    eligible_at: datetime


BodyModel = (
    LearningOutcomeResultBody
    | CourseCompletedBody
    | BadgeAwardedBody
    | CredentialEligibleBody
)

__all__ = [
    "EventType",
    "CANVAS_EVENT_NAMES",
    "canvas_event_name",
    "EventMetadata",
    "LiveEventEnvelope",
    "LearningOutcomeResultBody",
    "CourseCompletedBody",
    "BadgeAwardedBody",
    "CredentialEligibleBody",
    "BodyModel",
]
