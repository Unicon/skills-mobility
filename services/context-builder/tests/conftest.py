"""Test fixtures: a hermetic in-memory LMS client + the loaded profiles.

The fake client maps exact request paths to canned responses, modeling the
Mock LMS Resource API shapes. Unmapped paths return a Canvas-style 404 so a
mis-built URL surfaces as a failed fetch rather than passing silently.
"""

from __future__ import annotations

from typing import Any

import pytest
from context_builder.lms_client import LMSResponse
from context_builder.profiles import FetchProfile, load_profiles


class FakeLMSClient:
    def __init__(self, responses: dict[str, tuple[int, Any]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, path: str) -> LMSResponse:
        self.calls.append(path)
        if path in self.responses:
            status, data = self.responses[path]
            return LMSResponse(status_code=status, data=data)
        return LMSResponse(404, {"detail": {"errors": [{"message": f"not found: {path}"}]}})


@pytest.fixture
def profiles() -> dict[str, FetchProfile]:
    return load_profiles()


@pytest.fixture
def fake_client():
    def _make(responses: dict[str, tuple[int, Any]]) -> FakeLMSClient:
        return FakeLMSClient(responses)

    return _make
