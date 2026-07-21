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

    # Well-formedness check only: required-key *presence*, not JSON-Schema type
    # or non-null value validation (deliberately light for the POC).
    required: list[str] = request.target_schema.get("required", [])
    if required:
        missing = [k for k in required if k not in result]
        if missing:
            return ExecutionResponse.failed(
                transformation_type=request.transformation_type,
                error_type="malformed_output",
                message=f"output missing required target field(s): {missing}",
            )

    return ExecutionResponse.succeeded(
        transformation_type=request.transformation_type,
        result=result,
    )
