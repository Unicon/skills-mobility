"""Build Canvas Live Events-style envelopes from a triggered Action.

An Action is "grade an assignment". The event type is **derived** from the
course kind and the graded assignment's role (design §2 matrix); the body is
read from the catalog for the target learner. The happy/edge variant is inherent
in the data the Action references — which outcome (competency vs sub-competency)
or badge (accepted vs unaccepted), and the learner's grade (passing vs failing).

Every id referenced is resolved against the store; missing data raises
``EventBuildError`` so a broken Action fails fast at emit time rather than
producing an event the Context Builder can't resolve (requirements §5.2 FR-P3).
"""

from __future__ import annotations

from typing import Any

from skills_mobility_events import (
    BadgeAwardedBody,
    CourseCompletedBody,
    CourseRef,
    EventMetadata,
    EventType,
    LearningOutcomeResultBody,
    LiveEventEnvelope,
    canvas_event_name,
    new_event_id,
    now_utc,
)

from mock_lms.catalog import (
    ROOT_ACCOUNT_ID,
    Action,
    Assignment,
    AssignmentRole,
    CatalogStore,
    Course,
    CourseKind,
    User,
)


class EventBuildError(ValueError):
    """Raised when an Action references data not present in the store."""


def action_event_type(course: Course, assignment: Assignment) -> EventType:
    """Derive the event type from course kind + graded assignment role (§2 matrix)."""
    if course.kind is CourseKind.DIGITAL_CREDENTIAL:
        return EventType.BADGE_AWARDED
    if assignment.role is AssignmentRole.FINAL:
        return EventType.COURSE_COMPLETED
    return EventType.SKILL_MASTERED


def resolve_targets(
    store: CatalogStore, action: Action, scope: str, user_id: str | None
) -> list[User]:
    """Which learners an Action run emits for (scope ``one`` | ``all``)."""
    enrolled = [
        u
        for e in store.enrollments(action.course_id)
        if (u := store.get_user(e.user_id)) is not None
    ]
    if scope == "all":
        return enrolled
    if scope != "one":
        raise EventBuildError(f"Unknown scope: {scope!r} (expected 'one' or 'all')")
    if user_id is not None:
        target = next((u for u in enrolled if u.id == user_id), None)
        if target is None:
            raise EventBuildError(
                f"user {user_id!r} is not enrolled in course {action.course_id!r}"
            )
        return [target]
    if not enrolled:
        raise EventBuildError(f"course {action.course_id!r} has no enrolled learners")
    return [enrolled[0]]


def build_envelope(
    store: CatalogStore,
    action: Action,
    user: User,
    *,
    correlation_id: str,
    root_account_uuid: str,
) -> LiveEventEnvelope:
    course = store.get_course(action.course_id)
    if course is None:
        raise EventBuildError(f"Unknown course_id: {action.course_id!r}")
    assignment = store.get_assignment(action.assignment_id)
    if assignment is None:
        raise EventBuildError(f"Unknown assignment_id: {action.assignment_id!r}")

    event_type = action_event_type(course, assignment)
    if event_type is EventType.SKILL_MASTERED:
        body = _skill_mastered_body(store, assignment, user)
    elif event_type is EventType.COURSE_COMPLETED:
        body = _course_completed_body(store, assignment, user)
    else:
        body = _badge_awarded_body(store, assignment, user)

    metadata = EventMetadata(
        event_name=canvas_event_name(event_type),
        event_time=now_utc(),
        root_account_id=ROOT_ACCOUNT_ID,
        root_account_uuid=root_account_uuid,
        user_id=user.id,
        context_type="Course",
        context_id=course.id,
        event_id=new_event_id(),
        correlation_id=correlation_id,
        action_id=action.id,
    )
    return LiveEventEnvelope(metadata=metadata, body=body)


def _skill_mastered_body(store: CatalogStore, assignment: Assignment, user: User) -> dict[str, Any]:
    if not assignment.outcome_id:
        raise EventBuildError(f"assignment {assignment.id!r} has no aligned outcome")
    outcome = store.get_outcome(assignment.outcome_id)
    if outcome is None:
        raise EventBuildError(f"Unknown outcome_id: {assignment.outcome_id!r}")

    result = store.outcome_result(assignment.course_id, user.id, outcome.id)
    return LearningOutcomeResultBody(
        learning_outcome_result_id=(result.id if result else f"lor-{outcome.id}-{user.id}"),
        learning_outcome_id=outcome.id,
        result_id=result.id if result else None,
        score=result.score if result else outcome.mastery_points,
        possible=result.possible if result else outcome.points_possible,
        mastery=result.mastery if result else True,
        title=outcome.title,
        result_context_type="Course",
        result_context_id=assignment.course_id,
        associated_asset_type="Assignment",
        associated_asset_id=assignment.id,
        user_uuid=user.uuid,
        submitted_or_assessed_at=(result.submitted_or_assessed_at if result else now_utc()),
    ).model_dump(mode="json")


def _course_completed_body(
    store: CatalogStore, assignment: Assignment, user: User
) -> dict[str, Any]:
    submission = store.submission(assignment.course_id, assignment.id, user.id)
    enrollment = store.enrollment(assignment.course_id, user.id)
    score = submission.score if submission and submission.score is not None else None
    grade = (submission.grade if submission else None) or (
        enrollment.current_grade if enrollment else None
    )
    course = store.get_course(assignment.course_id)
    return CourseCompletedBody(
        course=CourseRef(id=assignment.course_id, name=course.name if course else None),
        completed_at=now_utc(),
        progress_percent=100.0,
        final_grade=grade,
        final_score=score,
    ).model_dump(mode="json")


def _badge_awarded_body(store: CatalogStore, assignment: Assignment, user: User) -> dict[str, Any]:
    if not assignment.badge_id:
        raise EventBuildError(f"assignment {assignment.id!r} has no associated badge")
    badge = store.get_badge(assignment.badge_id)
    if badge is None:
        raise EventBuildError(f"Unknown badge_id: {assignment.badge_id!r}")
    return BadgeAwardedBody(
        badge_id=badge.id,
        badge_name=badge.name,
        user_id=user.id,
        course_id=assignment.course_id,
        outcome_id=badge.outcome_id,
        awarded_at=now_utc(),
        criteria=badge.criteria or None,
    ).model_dump(mode="json")
