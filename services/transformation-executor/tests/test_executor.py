"""Unit tests for the transformation_executor.executor module."""

from __future__ import annotations

from transformation_executor.contracts import ExecutionRequest
from transformation_executor.executor import run


def _req(**kwargs) -> ExecutionRequest:  # type: ignore[no-untyped-def]
    defaults: dict = {
        "execution_id": "test-exec",
        "transformation_type": "learncard",
        "mapping": '{ "name": source_payloads.c.name }',
        "source_payloads": {"c": {"name": "Alice"}},
    }
    defaults.update(kwargs)
    return ExecutionRequest(**defaults)


def test_happy_path_maps_source_and_synthesized() -> None:
    req = _req(
        mapping='{ "name": source_payloads.c.name, "d": synthesized.x }',
        source_payloads={"c": {"name": "Alice"}},
        synthesized={"x": 99},
    )
    resp = run(req)
    assert resp.status == "succeeded"
    assert resp.result == {"name": "Alice", "d": 99}
    assert resp.error is None


def test_parse_error_returns_failed() -> None:
    req = _req(mapping="{invalid")
    resp = run(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.error_type == "parse_error"
    assert resp.result is None


def test_scalar_output_returns_malformed_output() -> None:
    # A mapping that returns a string (not a dict) must be caught.
    req = _req(
        mapping="source_payloads.c.name",
        source_payloads={"c": {"name": "Alice"}},
    )
    resp = run(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.error_type == "malformed_output"


def test_synthesized_substitution() -> None:
    req = _req(
        mapping='{ "score": synthesized.score }',
        synthesized={"score": 42},
    )
    resp = run(req)
    assert resp.status == "succeeded"
    assert resp.result == {"score": 42}


def test_missing_source_path_no_exception_escapes() -> None:
    # A reference to a missing key must not raise — JSONata returns null/undefined;
    # the executor either succeeds (with a null value) or fails cleanly.
    req = _req(
        mapping='{ "val": source_payloads.missing.field }',
        source_payloads={},
    )
    resp = run(req)
    # Either a succeeded dict (with null/None value) or a failed response — never an exception.
    assert resp.status in ("succeeded", "failed")
    if resp.status == "succeeded":
        assert isinstance(resp.result, dict)
    else:
        assert resp.error is not None


def test_target_schema_with_all_required_keys_present_succeeds() -> None:
    req = _req(
        mapping='{ "name": source_payloads.c.name, "score": synthesized.s }',
        source_payloads={"c": {"name": "Alice"}},
        synthesized={"s": 100},
        target_schema={"required": ["name", "score"]},
    )
    resp = run(req)
    assert resp.status == "succeeded"
    assert resp.result == {"name": "Alice", "score": 100}


def test_target_schema_missing_required_key_returns_failed() -> None:
    req = _req(
        mapping='{ "name": source_payloads.c.name }',
        source_payloads={"c": {"name": "Alice"}},
        target_schema={"required": ["name", "score"]},
    )
    resp = run(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.error_type == "malformed_output"
    assert "score" in resp.error.message


def test_empty_target_schema_skips_validation() -> None:
    req = _req(
        mapping='{ "name": source_payloads.c.name }',
        source_payloads={"c": {"name": "Alice"}},
        target_schema={},
    )
    resp = run(req)
    assert resp.status == "succeeded"


def test_transformation_type_preserved_on_all_paths() -> None:
    ttype = "smartresume"
    req = _req(transformation_type=ttype, mapping="{invalid")
    assert run(req).transformation_type == ttype

    req2 = _req(transformation_type=ttype, mapping="source_payloads.c.name")
    assert run(req2).transformation_type == ttype

    req3 = _req(transformation_type=ttype, mapping='{ "k": 1 }')
    assert run(req3).transformation_type == ttype
