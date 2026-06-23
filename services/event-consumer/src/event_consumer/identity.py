"""Envelope validation and stable event-identity derivation.

The required-field rules (FR-EC-9) and the idempotency key (FR-EC-11) are keyed
on the **business** fields the producer emits, not the per-delivery ``event_id``
— so a redelivered event dedupes, while the Mock LMS Reset (which clears the
idempotency store) lets a demo re-run the same scenario.
"""

from __future__ import annotations

from typing import Any

# Canvas event_name → internal event type.
CANVAS_TO_EVENT_TYPE = {
    "learning_outcome_result_created": "skill_mastered",
    "course_completed": "course_completed",
    "badge_awarded": "badge_awarded",
}

_REQUIRED_METADATA = ("event_name", "event_id", "correlation_id", "user_id")

# Per event type: (dotted path to the object id used in the identity key, label).
_IDENTITY_OBJECT = {
    "skill_mastered": "body.learning_outcome_id",
    "course_completed": "metadata.context_id",
    "badge_awarded": "body.badge_id",
}


def _dig(event: dict[str, Any], path: str) -> Any:
    cur: Any = event
    for seg in path.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return None
        cur = cur[seg]
    return cur


def event_type(event: dict[str, Any]) -> str | None:
    return CANVAS_TO_EVENT_TYPE.get(_dig(event, "metadata.event_name") or "")


def validate(event: dict[str, Any]) -> list[str]:
    """Return a list of validation errors (empty = valid)."""
    errors: list[str] = []
    for field in _REQUIRED_METADATA:
        if not _dig(event, f"metadata.{field}"):
            errors.append(f"missing required field metadata.{field}")
    etype = event_type(event)
    if etype is None:
        errors.append(f"unrecognized metadata.event_name: {_dig(event, 'metadata.event_name')!r}")
    else:
        object_path = _IDENTITY_OBJECT[etype]
        if not _dig(event, object_path):
            errors.append(f"missing required field {object_path} for {etype}")
    return errors


def identity_key(event: dict[str, Any]) -> str:
    """Stable key: ``event_name | user_id | <event-type object id>`` (FR-EC-11)."""
    etype = event_type(event)
    object_id = _dig(event, _IDENTITY_OBJECT[etype]) if etype else None
    return "|".join(
        [
            str(_dig(event, "metadata.event_name")),
            str(_dig(event, "metadata.user_id")),
            str(object_id),
        ]
    )


def rejection_key(event: dict[str, Any]) -> str:
    """Key for a rejected (malformed) event: raw event_id, else a generated id
    when the identity fields are missing (FR-EC-10)."""
    import uuid

    return _dig(event, "metadata.event_id") or f"rej_{uuid.uuid4().hex[:12]}"
