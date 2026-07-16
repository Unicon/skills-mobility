"""Normalize SmartResume delivery outcomes into the adapter response (design §2).

A 200 with a ``redirect_url`` becomes a ``succeeded`` result whose
``external_reference_id`` is the redirect URL (FR-SR-9). Any other status
becomes a ``failed`` result preserving the HTTP status code and SmartResume
error body (FR-SR-10).
"""

from __future__ import annotations

from typing import Any

import httpx

from smartresume_adapter.schemas import DeliverRequest, DeliverResponse, ErrorInfo


def _json_body(resp: httpx.Response) -> dict[str, Any] | None:
    try:
        body = resp.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def to_result(req: DeliverRequest, resp: httpx.Response) -> DeliverResponse:
    body = _json_body(resp)
    if resp.status_code == 200 and body is not None:
        redirect_url: str = body["redirect_url"]
        return DeliverResponse(
            status="succeeded",
            workflow_id=req.workflow_id,
            execution_id=req.execution_id,
            step_id=req.step_id,
            correlation_id=req.correlation_id,
            external_reference_id=redirect_url,
            result={"redirect_url": redirect_url},
        )
    return to_error(
        req,
        message=f"SmartResume delivery failed with HTTP {resp.status_code}",
        http_status=resp.status_code,
        body=body,
    )


def to_error(
    req: DeliverRequest,
    message: str,
    http_status: int | None = None,
    body: dict[str, Any] | None = None,
) -> DeliverResponse:
    return DeliverResponse(
        status="failed",
        workflow_id=req.workflow_id,
        execution_id=req.execution_id,
        step_id=req.step_id,
        correlation_id=req.correlation_id,
        error=ErrorInfo(message=message, http_status=http_status, body=body),
    )
