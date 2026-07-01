"""Normalize LearnCard delivery outcomes into the adapter response (design §2)."""

from __future__ import annotations

from learncard_wallet_adapter.schemas import DeliverResponse, DeliverResult, ErrorInfo


def to_success(external_reference_id: str) -> DeliverResponse:
    return DeliverResponse(
        status="succeeded",
        external_reference_id=external_reference_id,
        result=DeliverResult(delivery_state="accepted"),
    )


def to_error(message: str) -> DeliverResponse:
    return DeliverResponse(status="failed", error=ErrorInfo(message=message))
