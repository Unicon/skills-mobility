"""Fixtures: an in-memory store, a TestClient over an in-memory store, and
factory fixtures for sample Option-A envelopes (only the fields the Event
Consumer reads)."""

from __future__ import annotations

from typing import Any

import pytest
from event_consumer.app import create_app
from event_consumer.config import Settings
from event_consumer.store import SqliteStore
from fastapi.testclient import TestClient


@pytest.fixture
def store() -> SqliteStore:
    return SqliteStore(":memory:")


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(Settings(db_path=":memory:")))


@pytest.fixture
def skill_event():
    def _make(
        event_id: str = "evt_1", user_id: str = "U1", outcome: str = "OUT1"
    ) -> dict[str, Any]:
        return {
            "metadata": {
                "event_name": "learning_outcome_result_created",
                "event_id": event_id,
                "correlation_id": "corr_1",
                "user_id": user_id,
            },
            "body": {"learning_outcome_id": outcome},
        }

    return _make


@pytest.fixture
def course_event():
    def _make(event_id: str = "evt_2", user_id: str = "U1", course: str = "C1") -> dict[str, Any]:
        return {
            "metadata": {
                "event_name": "course_completed",
                "event_id": event_id,
                "correlation_id": "corr_2",
                "user_id": user_id,
                "context_id": course,
            },
            "body": {},
        }

    return _make


@pytest.fixture
def badge_event():
    def _make(event_id: str = "evt_3", user_id: str = "U1", badge: str = "B1") -> dict[str, Any]:
        return {
            "metadata": {
                "event_name": "badge_awarded",
                "event_id": event_id,
                "correlation_id": "corr_3",
                "user_id": user_id,
            },
            "body": {"badge_id": badge},
        }

    return _make
