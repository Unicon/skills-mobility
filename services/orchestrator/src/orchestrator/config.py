"""Settings for the Orchestrator."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")

    # Execution-log store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "orchestrator.db"
    # Issuer identity stamped into the stubbed OBv3 credential.
    issuer_id: str = "did:web:poc.skills-mobility.example"


@lru_cache
def get_settings() -> Settings:
    return Settings()
