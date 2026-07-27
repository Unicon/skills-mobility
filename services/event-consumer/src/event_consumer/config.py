"""Settings for the Event Consumer."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/event-consumer/), not a bare
# ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) silently ignored a service-dir .env. In
# containers this path doesn't exist and env comes from compose `environment:`,
# so it's harmlessly ignored there.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EVENT_CONSUMER_", env_file=_ENV_FILE, extra="ignore"
    )

    # Local inspectable store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "event-consumer.db"

    # When set, hand off to the real Orchestrator over HTTP; else capture-mode (ADR-0015).
    orchestrator_url: str | None = None

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
