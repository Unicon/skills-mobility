"""Runtime configuration for the Mock LMS service."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOCK_LMS_", env_file=".env", extra="ignore")

    # "local" (in-process capture) or "eventbridge" (AWS). See emission.py.
    emitter: str = "local"
    event_bus_name: str = "skills-mobility-poc"
    aws_region: str = "us-east-1"

    # POC identity (ADR-0002: CloudFront-layer auth). Role is injected via header;
    # this is the fallback when none is present (e.g. local dev / tests).
    default_role: str = "instructor"
    root_account_uuid: str = "mock-root-account"

    # Max emission-log entries kept in memory for the live feed / backfill.
    emission_log_capacity: int = 500

    # Load fixtures from this filesystem dir instead of the packaged (committed)
    # snapshot — e.g. point at generated-fixtures/ for a larger generated set.
    fixtures_dir: str | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
