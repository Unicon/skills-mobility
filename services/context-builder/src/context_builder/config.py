"""Settings for the Context Builder (MOCK_LMS base URL, etc.)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/context-builder/), not a bare
# ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) silently ignored a service-dir .env. In
# containers this path doesn't exist and env comes from compose `environment:`,
# so it's harmlessly ignored there.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXT_BUILDER_", env_file=_ENV_FILE, extra="ignore"
    )

    # Base URL of the Mock LMS Resource APIs the fetch profiles read.
    lms_base_url: str = "http://127.0.0.1:8000"

    # Root log level for the service entrypoint (INFO, DEBUG, WARNING, ...).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
