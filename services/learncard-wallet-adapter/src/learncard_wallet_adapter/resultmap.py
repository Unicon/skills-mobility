"""Normalize LearnCard delivery outcomes into the adapter response (design §2)."""

from __future__ import annotations

from learncard_wallet_adapter.schemas import (
    DeliverRequest,
    DeliverResponse,
    DeliverResult,
    ErrorInfo,
)


def to_success(req: DeliverRequest, external_reference_id: str) -> DeliverResponse:
    return DeliverResponse(
        status="succeeded",
        workflow_id=req.workflow_id,
        execution_id=req.execution_id,
        step_id=req.step_id,
        correlation_id=req.correlation_id,
        external_reference_id=external_reference_id,
        result=DeliverResult(delivery_state="accepted"),
    )


def to_error(req: DeliverRequest, message: str) -> DeliverResponse:
    return DeliverResponse(
        status="failed",
        workflow_id=req.workflow_id,
        execution_id=req.execution_id,
        step_id=req.step_id,
        correlation_id=req.correlation_id,
        error=ErrorInfo(message=message),
    )
