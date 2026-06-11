"""Build Canvas Live Events-style envelopes from a trigger + scenario data.

Every id referenced in an event body is resolved against the store; an unknown
id raises ``EventBuildError`` so a broken scenario fails fast at emit time
rather than producing an event the Context Builder can't resolve
(requirements §5.2 FR-P3).
"""

from __future__ import annotations

from typing import Any

from skills_mobility_events import (
    BadgeAwardedBody,
    CourseCompletedBody,
    CredentialEligibleBody,
    EventMetadata,
    EventType,
    LearningOutcomeResultBody,
    LiveEventEnvelope,
    canvas_event_name,
    new_event_id,
    now_utc,
)

from mock_lms.scenarios import EventSpec, ScenarioStore


class EventBuildError(ValueError):
    """Raised when a trigger references data not present in the store."""


def _require_course(store: ScenarioStore, course_id: str) -> None:
    if store.get_course(course_id) is None:
        raise EventBuildError(f"Unknown course_id: {course_id!r}")


def _require_student(store: ScenarioStore, user_id: str) -> None:
    if store.get_student(user_id) is None:
        raise EventBuildError(f"Unknown user_id: {user_id!r}")


def build_envelope(
    store: ScenarioStore,
    spec: EventSpec,
    *,
    correlation_id: str,
    scenario_id: str | None,
    root_account_uuid: str,
) -> LiveEventEnvelope:
    event_type = EventType(spec.event_type)
    _require_course(store, spec.course_id)
    _require_student(store, spec.user_id)

    if event_type is EventType.SKILL_MASTERED:
        body = _skill_mastered_body(store, spec)
    elif event_type is EventType.COURSE_COMPLETED:
        body = _course_completed_body(spec)
    elif event_type is EventType.BADGE_AWARDED:
        body = _badge_awarded_body(store, spec)
    elif event_type is EventType.CREDENTIAL_ELIGIBLE:
        body = _credential_eligible_body(spec)
    else:  # pragma: no cover - exhaustive above
        raise EventBuildError(f"Unsupported event_type: {spec.event_type!r}")

    metadata = EventMetadata(
        event_name=canvas_event_name(event_type),
        event_time=now_utc(),
        root_account_uuid=root_account_uuid,
        user_id=spec.user_id,
        context_type="Course",
        context_id=spec.course_id,
        event_id=new_event_id(),
        correlation_id=correlation_id,
        scenario_id=scenario_id,
    )
    return LiveEventEnvelope(metadata=metadata, body=body)


def _skill_mastered_body(store: ScenarioStore, spec: EventSpec) -> dict[str, Any]:
    if not spec.outcome_id:
        raise EventBuildError("skill_mastered requires outcome_id")
    outcome = store.get_outcome(spec.outcome_id)
    if outcome is None:
        raise EventBuildError(f"Unknown outcome_id: {spec.outcome_id!r}")
    if spec.assignment_id and store.get_assignment(spec.assignment_id) is None:
        raise EventBuildError(f"Unknown assignment_id: {spec.assignment_id!r}")

    # Prefer a recorded outcome result if the scenario has one; else synthesize mastery.
    results = store.outcome_results(
        spec.course_id, user_ids=[spec.user_id], outcome_ids=[spec.outcome_id]
    )
    result = results[0] if results else None
    return LearningOutcomeResultBody(
        learning_outcome_result_id=result.id if result else f"lor-{spec.outcome_id}-{spec.user_id}",
        learning_outcome_id=spec.outcome_id,
        user_id=spec.user_id,
        course_id=spec.course_id,
        score=result.score if result else outcome.mastery_points,
        possible=result.possible if result else outcome.points_possible,
        mastery=result.mastery if result else True,
        title=outcome.title,
        assignment_id=spec.assignment_id or (result.assignment_id if result else None),
        submitted_or_assessed_at=result.submitted_or_assessed_at if result else now_utc(),
    ).model_dump(mode="json")


def _course_completed_body(spec: EventSpec) -> dict[str, Any]:
    return CourseCompletedBody(
        course_id=spec.course_id,
        user_id=spec.user_id,
        completed_at=now_utc(),
    ).model_dump(mode="json")


def _badge_awarded_body(store: ScenarioStore, spec: EventSpec) -> dict[str, Any]:
    if spec.outcome_id and store.get_outcome(spec.outcome_id) is None:
        raise EventBuildError(f"Unknown outcome_id: {spec.outcome_id!r}")
    badge_name = spec.badge_name or "Skill Badge"
    return BadgeAwardedBody(
        badge_id=spec.badge_id or f"badge-{spec.course_id}-{spec.user_id}",
        badge_name=badge_name,
        user_id=spec.user_id,
        course_id=spec.course_id,
        outcome_id=spec.outcome_id,
        awarded_at=now_utc(),
    ).model_dump(mode="json")


def _credential_eligible_body(spec: EventSpec) -> dict[str, Any]:
    return CredentialEligibleBody(
        user_id=spec.user_id,
        course_id=spec.course_id,
        credential_type=spec.credential_type or "open-badge",
        eligible_at=now_utc(),
    ).model_dump(mode="json")
