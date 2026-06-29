"""Context Builder behavior: profile selection, chained fetches, error capture,
and failure responses — exercised end to end through ``build_context`` against a
hermetic fake LMS client."""

from __future__ import annotations

from typing import Any

from context_builder.builder import build_context
from context_builder.schemas import BuildRequest, ContextBundle, FailureResponse

SKILL_EVENT = {
    "metadata": {
        "event_name": "learning_outcome_result_created",
        "event_id": "EV1",
        "correlation_id": "CORR1",
        "root_account_id": "1",
        "user_id": "U1",
    },
    "body": {
        "learning_outcome_id": "OUT1",
        "result_context_type": "Course",
        "result_context_id": "C1",
        "associated_asset_type": "Assignment",
        "associated_asset_id": "A1",
        "user_uuid": "UU1",
    },
}

_SUBMISSION_URL = (
    "/api/v1/courses/C1/assignments/A1/submissions/U1?include[]=rubric_assessment"
)

SKILL_RESPONSES: dict[str, tuple[int, Any]] = {
    "/api/v1/outcomes/OUT1": (200, {"id": "OUT1", "title": "1.0.0 Principles"}),
    "/api/v1/courses/C1/assignments/A1": (200, {"id": "A1", "rubric_id": "RUB1"}),
    "/api/v1/courses/C1/rubrics/RUB1": (200, {"id": "RUB1", "criteria": [{"id": "c1"}]}),
    "/api/v1/courses/C1/modules?include[]=items": (
        200,
        [
            {"id": "MOD0", "items": []},
            {
                "id": "MOD1",
                "items": [
                    {"id": "I1", "type": "Assignment", "content_id": "A1"},
                    {"id": "I2", "type": "Page", "content_id": "P1"},
                ],
            },
        ],
    ),
    "/api/v1/courses/C1/pages/P1": (200, {"id": "P1", "title": "Overview"}),
    "/api/v1/accounts/1/users?uuids[]=UU1": (200, [{"id": "U1", "uuid": "UU1"}]),
    _SUBMISSION_URL: (200, {"user_id": "U1", "score": 92}),
}


def _build(execution_id, event, client, profiles):
    return build_context(BuildRequest(execution_id=execution_id, event=event), client, profiles)


def test_skill_mastered_full_chain(profiles, fake_client):
    client = fake_client(SKILL_RESPONSES)
    result = _build("e1", SKILL_EVENT, client, profiles)
    assert isinstance(result, ContextBundle)
    assert result.event_type == "skill_mastered"
    assert result.fetch_profile_id == "skill_mastered.v1"
    # Trace fields carried from the event for downstream auditability (FR-CB7).
    assert result.event_id == "EV1"
    assert result.correlation_id == "CORR1"
    sd = result.source_data
    assert sd["outcome"]["id"] == "OUT1"
    assert sd["assignment"]["id"] == "A1"
    assert sd["rubric"]["id"] == "RUB1"  # conditional step ran (assignment had rubric_id)
    assert sd["module_context"]["id"] == "MOD1"  # select picked the module containing A1
    assert sd["module_pages"][0]["id"] == "P1"  # for_each over the module's Page items
    # The account-user lookup resolved the Canvas user_id (chained into the submission fetch).
    assert sd["canvas_user"][0]["id"] == "U1"
    # The submission fetch was keyed by the user_id resolved from the account lookup.
    assert sd["submission"]["user_id"] == "U1"
    assert _SUBMISSION_URL in client.calls


def test_skill_mastered_rubric_step_skipped_when_no_rubric_id(profiles, fake_client):
    responses = dict(SKILL_RESPONSES)
    responses["/api/v1/courses/C1/assignments/A1"] = (200, {"id": "A1"})  # no rubric_id
    del responses["/api/v1/courses/C1/rubrics/RUB1"]
    result = _build("e1", SKILL_EVENT, fake_client(responses), profiles)
    assert isinstance(result, ContextBundle)
    assert "rubric" not in result.source_data  # condition absent → step skipped


def test_failed_fetch_becomes_error_object_in_bundle(profiles, fake_client):
    responses = dict(SKILL_RESPONSES)
    responses[_SUBMISSION_URL] = (
        404,
        {"detail": {"errors": [{"message": "submission not found"}]}},
    )
    result = _build("e1", SKILL_EVENT, fake_client(responses), profiles)
    assert isinstance(result, ContextBundle)
    assert result.source_data["submission"]["error"]["status_code"] == 404
    assert result.source_data["outcome"]["id"] == "OUT1"  # other fetches still succeeded


def test_course_completed_happy_path(profiles, fake_client):
    event = {
        "metadata": {"event_name": "course_completed", "user_id": "U1"},
        "body": {"course": {"id": "C1"}},
    }
    responses: dict[str, tuple[int, Any]] = {
        "/api/v1/courses/C1": (200, {"id": "C1", "name": "Accounting"}),
        "/api/v1/users/U1/profile": (200, {"id": "U1", "email": "a@b.c"}),
        "/api/v1/courses/C1/enrollments?user_id=U1": (
            200,
            [{"user_id": "U1", "current_grade": "A"}],
        ),
        "/api/v1/courses/C1/modules?include[]=items": (
            200,
            [{"id": "MOD1", "name": "Unit 1", "items": [{"id": "I1", "type": "Page"}]}],
        ),
        "/api/v1/courses/C1/pages": (200, [{"id": "P1", "title": "Overview"}]),
        "/api/v1/courses/C1/assignments": (200, [{"id": "A1", "name": "Final"}]),
        "/api/v1/courses/C1/rubrics": (200, [{"id": "RUB1", "title": "Final rubric"}]),
        "/api/v1/courses/C1/students/submissions?student_ids[]=U1": (
            200,
            [{"user_id": "U1", "score": 95}],
        ),
    }
    client = fake_client(responses)
    result = _build("e2", event, client, profiles)
    assert isinstance(result, ContextBundle)
    assert result.event_type == "course_completed"
    assert result.fetch_profile_id == "course_completed.v1"
    sd = result.source_data
    # All eight output keys are present with real (non-empty) data flowing through.
    assert sd["course"] == {"id": "C1", "name": "Accounting"}
    assert sd["learner_profile"] == {"id": "U1", "email": "a@b.c"}
    assert sd["enrollment"][0]["current_grade"] == "A"
    assert sd["modules"][0]["id"] == "MOD1"
    assert sd["pages"][0]["title"] == "Overview"
    assert sd["assignments"][0]["name"] == "Final"
    assert sd["rubrics"][0]["id"] == "RUB1"
    assert sd["submissions"][0]["score"] == 95
    # The submissions fetch was keyed by the event's user_id.
    assert "/api/v1/courses/C1/students/submissions?student_ids[]=U1" in client.calls


def test_badge_awarded_happy_and_unaccepted(profiles, fake_client):
    event = {
        "metadata": {"event_name": "badge_awarded"},
        "body": {"badge_id": "B1", "user_id": "U1"},
    }
    ok = fake_client(
        {"/api/v1/badges/B1": (200, {"id": "B1"}), "/api/v1/users/U1/profile": (200, {"id": "U1"})}
    )
    res = build_context(BuildRequest(execution_id="e3", event=event), ok, profiles)
    assert isinstance(res, ContextBundle)
    assert res.source_data["badge"]["id"] == "B1"
    assert res.source_data["user_profile"]["id"] == "U1"

    # Unaccepted badge → GET badge 409 → error object under "badge".
    edge_event = {
        "metadata": {"event_name": "badge_awarded"},
        "body": {"badge_id": "B2", "user_id": "U1"},
    }
    edge = fake_client(
        {
            "/api/v1/badges/B2": (409, {"detail": "not accepted"}),
            "/api/v1/users/U1/profile": (200, {"id": "U1"}),
        }
    )
    res2 = build_context(BuildRequest(execution_id="e4", event=edge_event), edge, profiles)
    assert isinstance(res2, ContextBundle)
    assert res2.source_data["badge"]["error"]["status_code"] == 409


def test_unknown_event_type_returns_failure(profiles, fake_client):
    event = {"metadata": {"event_name": "mystery_event"}, "body": {}}
    result = _build("e5", event, fake_client({}), profiles)
    assert isinstance(result, FailureResponse)
    assert result.context_builder_error["code"] == "unrecognized_event_type"


def test_missing_required_identifier_returns_failure(profiles, fake_client):
    event = {
        "metadata": {
            "event_name": "learning_outcome_result_created",
            "root_account_id": "1",
            "user_id": "U1",
        },
        "body": {"result_context_id": "C1"},  # missing learning_outcome_id for the first step
    }
    result = _build("e6", event, fake_client({}), profiles)
    assert isinstance(result, FailureResponse)
    assert result.context_builder_error["code"] == "missing_required_identifier"
