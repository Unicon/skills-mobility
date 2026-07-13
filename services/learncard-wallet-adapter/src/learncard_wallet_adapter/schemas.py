"""Router-facing request/response contract for the wallet-delivery endpoint.

See docs/3_design/learncard-wallet-adapter.md §2. The Delivery Router owns the
outer delivery-action envelope; this adapter owns only the shapes below.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class DeliverPayload(BaseModel):
    # Already resolved by the upstream Profile Resolver step. Required: an absent
    # value is an upstream planning error (422), not something this adapter fixes.
    recipient_profile_id: str
    # The already-issued (signed) credential to deliver, verbatim.
    signed_credential: dict[str, Any]


class DeliverRequest(BaseModel):
    contract_version: Literal["v1"]
    workflow_id: str
    execution_id: str
    step_id: str
    correlation_id: str
    delivery_config_ref: str
    payload: DeliverPayload


class DeliverResult(BaseModel):
    delivery_state: str


class ErrorInfo(BaseModel):
    message: str


class DeliverResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    # Correlation identifiers preserved from the request (FR-LCW-11), so a delivery
    # outcome is traceable in the result record itself, not only via the logs.
    workflow_id: str = ""
    execution_id: str = ""
    step_id: str = ""
    correlation_id: str = ""
    external_reference_id: str | None = None
    result: DeliverResult | None = None
    error: ErrorInfo | None = None
