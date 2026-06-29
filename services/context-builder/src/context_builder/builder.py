"""Top-level orchestration: pick the fetch profile for an event, run it, and
assemble a context bundle (or a failure response)."""

from __future__ import annotations

import logging

from context_builder.engine import MissingIdentifier, run_profile
from context_builder.lms_client import LMSClient
from context_builder.profiles import FetchProfile
from context_builder.schemas import BuildRequest, ContextBundle, FailureResponse

logger = logging.getLogger(__name__)

# The event arrives with the Canvas ``event_name``; the profile is keyed by the
# internal event type. Resolve both (FR-CB2).
_CANVAS_TO_EVENT_TYPE = {
    "learning_outcome_result_created": "skill_mastered",
    "course_completed": "course_completed",
    "badge_awarded": "badge_awarded",
}


def build_context(
    request: BuildRequest,
    client: LMSClient,
    profiles: dict[str, FetchProfile],
) -> ContextBundle | FailureResponse:
    metadata = request.event.get("metadata", {})
    event_name = metadata.get("event_name")
    event_type = _CANVAS_TO_EVENT_TYPE.get(event_name or "", event_name or "")
    profile = profiles.get(event_type)
    if profile is None:
        logger.warning(
            "no fetch profile: execution_id=%s event_name=%s", request.execution_id, event_name
        )
        return FailureResponse(
            execution_id=request.execution_id,
            context_builder_error={
                "code": "unrecognized_event_type",
                "message": f"no fetch profile for event_name={event_name!r}",
            },
        )
    logger.info(
        "selected fetch profile: execution_id=%s event_name=%s profile=%s",
        request.execution_id,
        event_name,
        profile.id,
    )
    try:
        source_data = run_profile(profile, request.event, client)
    except MissingIdentifier as exc:
        logger.warning("profile could not start: execution_id=%s %s", request.execution_id, exc)
        return FailureResponse(
            execution_id=request.execution_id,
            context_builder_error={"code": "missing_required_identifier", "message": str(exc)},
        )
    logger.info(
        "context bundle assembled: execution_id=%s profile=%s keys=%s",
        request.execution_id,
        profile.id,
        sorted(source_data),
    )
    return ContextBundle(
        execution_id=request.execution_id,
        event_id=metadata.get("event_id", ""),
        correlation_id=metadata.get("correlation_id", ""),
        event_type=profile.event_type,
        fetch_profile_id=profile.id,
        source_data=source_data,
    )
