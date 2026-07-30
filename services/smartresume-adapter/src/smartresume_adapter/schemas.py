"""Router-facing request/response contract for the SmartResume-delivery endpoint.

See docs/3_design/smartresume-adapter.md §2. The Delivery Router owns the outer
delivery-action envelope; this adapter owns only the shapes below. The nested
``payload`` mirrors the SmartResume ``/credentials`` body (recipient +
credentials); the adapter maps it mechanically and never regenerates fields.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class Recipient(BaseModel):
    # Globally-unique learner identifier (e.g. an email URI). Required: an absent
    # value is an upstream planning error (422), not something this adapter fixes.
    id: str
    givenName: str | None = None
    familyName: str | None = None
    email: str | None = None
    phone: str | None = None
    studentId: str | None = None
    signupOrganization: str | None = None


class DeliverPayload(BaseModel):
    recipient: Recipient
    # Optional read-back token scoping the SmartResume redirect URL to this recipient.
    recipienttoken: str | None = None
    # Already shaped upstream as SmartResume credential entries (id, type, name,
    # credentialSubject, issuer, and an optional proof). Passed through mechanically.
    credentials: list[dict[str, Any]]


class DeliverRequest(BaseModel):
    contract_version: Literal["v1"]
    workflow_id: str
    execution_id: str
    step_id: str
    correlation_id: str
    delivery_config_ref: str
    payload: DeliverPayload


class ErrorInfo(BaseModel):
    # Structured failure detail preserving the SmartResume HTTP status + body
    # (FR-SR-10), never flattened to an opaque string.
    message: str
    http_status: int | None = None
    body: dict[str, Any] | None = None


class DeliverResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    # Correlation identifiers preserved from the request (FR-SR-12), so a delivery
    # outcome is traceable in the result record itself, not only via the logs.
    workflow_id: str = ""
    execution_id: str = ""
    step_id: str = ""
    correlation_id: str = ""
    # The SmartResume redirect_url on success (FR-SR-9).
    external_reference_id: str | None = None
    result: dict[str, Any] | None = None
    error: ErrorInfo | None = None
