"""Orchestrator-facing request/response contract for the resolver (design §2)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class LearnerIdType(StrEnum):
    # A LearnCard handle (== profileId): resolvable via Search Profiles.
    PROFILE_ID = "profile_id"
    # Email: accepted but not resolvable — LearnCard Search does not match email
    # and services can't create a learner's profile (verified live, #41 spike).
    EMAIL = "email"


class ResolvePayload(BaseModel):
    learner_id_type: LearnerIdType
    learner_id_value: str


class ResolveRequest(BaseModel):
    contract_version: Literal["v1"]
    workflow_id: str
    execution_id: str
    step_id: str
    correlation_id: str
    delivery_config_ref: str
    payload: ResolvePayload


class ResolvedProfile(BaseModel):
    profile_id: str
    did: str
    resolution_method: Literal["stored", "searched"]


class ErrorInfo(BaseModel):
    message: str


class ResolveResponse(BaseModel):
    # succeeded: result present. unresolved: no LearnCard profile for this learner
    # (a clean business outcome, not a fault). failed: API/transport error.
    status: Literal["succeeded", "unresolved", "failed"]
    result: ResolvedProfile | None = None
    error: ErrorInfo | None = None
