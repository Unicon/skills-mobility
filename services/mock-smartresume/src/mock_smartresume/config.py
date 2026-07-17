"""Settings for the Mock SmartResume (prefix: MOCK_SMARTRESUME_).

Stateless and secret-free — the mock accepts any non-empty ClientID/AccessKey.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/mock-smartresume/), not a bare
# ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) silently ignored a service-dir .env. In
# containers this path doesn't exist and env comes from compose `environment:`,
# so it's harmlessly ignored there.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOCK_SMARTRESUME_", env_file=_ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8930 — outside Consul's reserved range (8300-8302, 8500,
    # 8600) and clear of the other POC services (mock-lms 8000, orchestrator 8400,
    # delivery-router 8800, learncard-wallet 8900, learncard-issuer 8910,
    # smartresume-adapter 8920).
    port: int = 8930

    log_level: str = "INFO"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
