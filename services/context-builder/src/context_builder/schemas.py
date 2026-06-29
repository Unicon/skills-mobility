"""Orchestrator-facing request/response contracts (design §3).

The Context Builder always returns *either* a context bundle (with a
``source_data`` map; per-fetch failures appear as error objects under their
output key) *or* a distinct failure response with no ``source_data`` when it
cannot even begin executing the profile (FR-CB11/FR-CB12).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class BuildRequest(BaseModel):
    """What the Orchestrator sends: the raw event envelope + execution id."""

    execution_id: str
    event: dict[str, Any]


class FetchError(BaseModel):
    """Stored under a step's output key in place of the response when a fetch fails."""

    source_api: str
    status_code: int | None = None
    message: str


class ContextBundle(BaseModel):
    """Successful (or partial) result — one bundle of named source responses."""

    execution_id: str
    event_id: str = ""  # carried from the event for downstream auditability (FR-CB7)
    correlation_id: str = ""  # carried from the event for downstream auditability (FR-CB7)
    event_type: str
    fetch_profile_id: str
    source_data: dict[str, Any]


class FailureResponse(BaseModel):
    """Returned when the profile can't start (unknown event type, missing
    required identifier, profile not loadable). Has no ``source_data``."""

    execution_id: str
    context_builder_error: dict[str, str]
