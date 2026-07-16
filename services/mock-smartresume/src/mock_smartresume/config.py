"""Settings for the Mock SmartResume (prefix: MOCK_SMARTRESUME_).

Stateless and secret-free — the mock accepts any non-empty ClientID/AccessKey.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MOCK_SMARTRESUME_", env_file=".env", extra="ignore"
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
