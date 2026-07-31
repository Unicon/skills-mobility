"""Settings tests — FR-SR-13: ``api_url`` has no hardcoded default."""

from __future__ import annotations

import pydantic
import pytest
from smartresume_adapter.config import ENV_FILE, Settings


def test_api_url_is_required_with_no_default(monkeypatch, tmp_path) -> None:
    # FR-SR-13: the SmartResume base URL must be supplied explicitly — a missing
    # env var is a hard validation error, never a silent default endpoint.
    monkeypatch.delenv("SMARTRESUME_ADAPTER_API_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # keep any developer .env at the anchor out of play
    original = ENV_FILE.read_text() if ENV_FILE.exists() else None
    if original is not None:
        ENV_FILE.unlink()
    try:
        with pytest.raises(pydantic.ValidationError, match="api_url"):
            Settings()  # type: ignore[call-arg]
    finally:
        if original is not None:
            ENV_FILE.write_text(original)


def test_api_url_supplied_via_env(monkeypatch) -> None:
    monkeypatch.setenv("SMARTRESUME_ADAPTER_API_URL", "http://localhost:8930")
    assert Settings().api_url == "http://localhost:8930"
