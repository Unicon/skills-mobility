"""Runtime configuration for the Mock LMS service."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/mock-lms/), not a bare ".env":
# a relative env_file resolves against the process CWD, so running from the repo
# root (the documented way) silently ignored a service-dir .env. In containers
# this path doesn't exist and env comes from compose `environment:`, so it's
# harmlessly ignored there.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOCK_LMS_", env_file=_ENV_FILE, extra="ignore")

    # "local" (in-process capture) or "eventbridge" (AWS). See emitter.py.
    emitter: str = "local"
    event_bus_name: str = "skills-mobility-poc"
    aws_region: str = "us-east-1"

    # When set, the LocalEmitter also forwards each envelope to the Event
    # Consumer's /ingest (the local stand-in for EventBridge → Lambda).
    event_consumer_url: str | None = None

    # POC identity stamped into event metadata (ADR-0002: CloudFront-layer auth,
    # single demo user — no role split).
    root_account_uuid: str = "mock-root-account"

    # Load fixtures from this filesystem dir instead of the packaged (committed)
    # snapshot — e.g. point at generated-fixtures/ for a larger generated set.
    fixtures_dir: str | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
