"""API tests for the Transformation Executor."""

from __future__ import annotations

from fastapi.testclient import TestClient
from transformation_executor.app import create_app

ENDPOINT = "/execute"


def _client() -> TestClient:
    return TestClient(create_app())


def test_happy_path_returns_200_with_succeeded_result() -> None:
    body = _client().post(
        ENDPOINT,
        json={
            "execution_id": "exec-1",
            "transformation_type": "learncard",
            "mapping": '{ "name": source_payloads.lms.name }',
            "source_payloads": {"lms": {"name": "Alice"}},
        },
    ).json()
    assert body["status"] == "succeeded"
    assert isinstance(body["result"], dict)
    assert body["result"]["name"] == "Alice"
    assert body["error"] is None


def test_parse_error_returns_200_with_failed_status() -> None:
    body = _client().post(
        ENDPOINT,
        json={
            "execution_id": "exec-2",
            "transformation_type": "learncard",
            "mapping": "{bad mapping{{",
        },
    ).json()
    assert body["status"] == "failed"
    assert body["error"] is not None
    assert body["error"]["error_type"] == "parse_error"
    assert body["result"] is None


def test_missing_mapping_field_returns_422() -> None:
    resp = _client().post(
        ENDPOINT,
        json={
            "execution_id": "exec-3",
            "transformation_type": "learncard",
            # mapping omitted intentionally
        },
    )
    assert resp.status_code == 422


def test_healthz_returns_ok() -> None:
    resp = _client().get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
