"""Fixtures: a TestClient over an in-memory store, and a sample event."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from orchestrator.app import create_app
from orchestrator.config import Settings


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(db_path=":memory:")))


@pytest.fixture
def sample_event() -> dict[str, Any]:
    return {
        "metadata": {
            "event_name": "learning_outcome_result_created",
            "event_id": "evt_1",
            "correlation_id": "corr_1",
            "user_id": "WU1125875",
        },
        "body": {"learning_outcome_id": "OUT1"},
    }


@pytest.fixture
def course_event() -> dict[str, Any]:
    return {
        "metadata": {
            "event_name": "course_completed",
            "event_id": "evt_2",
            "correlation_id": "corr_2",
            "user_id": "WU1125875",
        },
        "body": {"course_id": "ACCY-111"},
    }
