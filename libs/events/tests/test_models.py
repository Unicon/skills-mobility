from datetime import UTC, datetime

from skills_mobility_events import (
    EventMetadata,
    EventType,
    LearningOutcomeResultBody,
    LiveEventEnvelope,
    canvas_event_name,
    new_correlation_id,
    new_event_id,
)


def test_canvas_event_name_mapping():
    assert canvas_event_name(EventType.SKILL_MASTERED) == "learning_outcome_result_created"
    assert canvas_event_name(EventType.COURSE_COMPLETED) == "course_completed"


def test_envelope_round_trips_to_json():
    body = LearningOutcomeResultBody(
        learning_outcome_result_id="lor-1",
        learning_outcome_id="3001",
        user_id="2001",
        course_id="1001",
        score=4.0,
        possible=5.0,
        mastery=True,
        title="Data Analysis",
        assignment_id="4001",
        submitted_or_assessed_at=datetime(2026, 6, 10, tzinfo=UTC),
    )
    env = LiveEventEnvelope(
        metadata=EventMetadata(
            event_name=canvas_event_name(EventType.SKILL_MASTERED),
            event_time=datetime(2026, 6, 10, 17, 0, tzinfo=UTC),
            user_id="2001",
            context_type="Course",
            context_id="1001",
            event_id=new_event_id(),
            correlation_id=new_correlation_id(),
            scenario_id="skill-mastered",
        ),
        body=body.model_dump(mode="json"),
    )
    dumped = env.model_dump(mode="json")
    assert dumped["metadata"]["event_name"] == "learning_outcome_result_created"
    assert dumped["body"]["mastery"] is True
    # Re-parse to confirm the contract is stable.
    assert LiveEventEnvelope.model_validate(dumped).metadata.context_id == "1001"


def test_ids_are_unique_and_prefixed():
    a, b = new_event_id(), new_event_id()
    assert a != b
    assert a.startswith("evt_")
    assert new_correlation_id().startswith("corr_")
