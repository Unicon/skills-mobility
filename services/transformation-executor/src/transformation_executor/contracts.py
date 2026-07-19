"""Request / response contracts for the Transformation Executor."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ExecutionRequest(BaseModel):
    execution_id: str
    event_id: str = ""
    correlation_id: str = ""
    transformation_type: str
    delivery_target: str | None = None
    mapping: str
    source_payloads: dict[str, Any] = {}
    synthesized: dict[str, Any] = {}


class ExecutionError(BaseModel):
    error_type: str
    message: str


class ExecutionResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    transformation_type: str
    result: dict[str, Any] | None = None
    error: ExecutionError | None = None

    @classmethod
    def succeeded(
        cls, *, transformation_type: str, result: dict[str, Any]
    ) -> ExecutionResponse:
        return cls(status="succeeded", transformation_type=transformation_type, result=result)

    @classmethod
    def failed(
        cls, *, transformation_type: str, error_type: str, message: str
    ) -> ExecutionResponse:
        return cls(
            status="failed",
            transformation_type=transformation_type,
            error=ExecutionError(error_type=error_type, message=message),
        )
