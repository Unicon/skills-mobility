"""Fixtures: a TestClient over an in-memory store, and a sample event."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from orchestrator.app import create_app
from orchestrator.config import Settings


@pytest.fixture
def client() -> TestClient:
    # Pin every seam URL to None so a developer's local .env can't turn the
    # stubs into real Http*Clients that fire at (or ConnectError against) live
    # services during tests — CWD-safe .env loading now finds a service-dir
    # .env regardless of where pytest runs. test_app's /run-workflow tests
    # exercise exactly these seams.
    return TestClient(
        create_app(
            Settings(
                db_path=":memory:",
                context_builder_url=None,
                profile_resolver_url=None,
                delivery_router_url=None,
                field_mapping_url=None,
                delivery_targets_url=None,
                workflow_actions_url=None,
            )
        )
    )


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
