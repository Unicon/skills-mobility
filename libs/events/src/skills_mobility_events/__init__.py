"""Shared event contracts for the Skills Mobility POC.

The Mock Event Producer owns these schemas; downstream consumers (Event
Consumer, Context Builder) treat them as the contract for events on the bus.
"""

from skills_mobility_events.ids import (
    new_correlation_id,
    new_emission_id,
    new_event_id,
    now_utc,
)
from skills_mobility_events.models import (
    CANVAS_EVENT_NAMES,
    BadgeAwardedBody,
    CourseCompletedBody,
    CourseRef,
    EventMetadata,
    EventType,
    LearningOutcomeResultBody,
    LiveEventEnvelope,
    canvas_event_name,
)

__all__ = [
    "new_correlation_id",
    "new_emission_id",
    "new_event_id",
    "now_utc",
    "CANVAS_EVENT_NAMES",
    "canvas_event_name",
    "EventType",
    "EventMetadata",
    "LiveEventEnvelope",
    "LearningOutcomeResultBody",
    "CourseRef",
    "CourseCompletedBody",
    "BadgeAwardedBody",
]
