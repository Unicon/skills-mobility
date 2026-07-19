"""Deterministic JSONata expression runner.

Takes an ``ExecutionRequest`` (mapping expression + assembled payloads) and
returns an ``ExecutionResponse``.  All failures are normalized — no exception
escapes this module.
"""

from __future__ import annotations

from typing import Any

import jsonata  # type: ignore[import-untyped]

from transformation_executor.contracts import ExecutionRequest, ExecutionResponse


def run(request: ExecutionRequest) -> ExecutionResponse:
    """Execute the JSONata mapping expression against the assembled context."""
    context: dict[str, Any] = {
        "source_payloads": request.source_payloads,
        "synthesized": request.synthesized,
    }

    try:
        expr = jsonata.Jsonata(request.mapping)
    except Exception as exc:
        return ExecutionResponse.failed(
            transformation_type=request.transformation_type,
            error_type="parse_error",
            message=str(exc),
        )

    try:
        result = expr.evaluate(context)
    except Exception as exc:
        return ExecutionResponse.failed(
            transformation_type=request.transformation_type,
            error_type="eval_error",
            message=str(exc),
        )

    if not isinstance(result, dict):
        return ExecutionResponse.failed(
            transformation_type=request.transformation_type,
            error_type="malformed_output",
            message=f"expected a JSON object, got {type(result).__name__}",
        )

    return ExecutionResponse.succeeded(
        transformation_type=request.transformation_type,
        result=result,
    )
