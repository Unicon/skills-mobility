"""Settings for the Event Consumer."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVENT_CONSUMER_")

    # Local inspectable store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "event-consumer.db"

    # When set, hand off to the real Orchestrator over HTTP; else capture-mode (ADR-0015).
    orchestrator_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
