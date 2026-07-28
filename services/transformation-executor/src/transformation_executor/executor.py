"""Deterministic JSONata expression runner.

Takes an ``ExecutionRequest`` (mapping expression + assembled payloads) and
returns an ``ExecutionResponse``.  All failures are normalized — no exception
escapes this module.
"""

from __future__ import annotations

from typing import Any

import jsonata  # type: ignore[import-untyped]
import jsonschema

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

    # Full JSON-Schema validation against the target schema (FR-TE-6/FR-TE-9,
    # design §7): types, required keys, and nested shapes — not just presence.
    # An empty target_schema ({}) validates everything, preserving the
    # no-schema-supplied behaviour.
    try:
        jsonschema.validate(result, request.target_schema)
    except jsonschema.SchemaError as exc:
        return ExecutionResponse.failed(
            transformation_type=request.transformation_type,
            error_type="malformed_output",
            message=f"target_schema is not a valid JSON Schema: {exc.message}",
        )
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "$"
        return ExecutionResponse.failed(
            transformation_type=request.transformation_type,
            error_type="malformed_output",
            message=f"output does not match target schema at {path}: {exc.message}",
        )

    return ExecutionResponse.succeeded(
        transformation_type=request.transformation_type,
        result=result,
    )
