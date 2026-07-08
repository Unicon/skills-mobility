"""Settings for the Context Builder (MOCK_LMS base URL, etc.)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CONTEXT_BUILDER_")

    # Base URL of the Mock LMS Resource APIs the fetch profiles read.
    lms_base_url: str = "http://127.0.0.1:8000"

    # Root log level for the service entrypoint (INFO, DEBUG, WARNING, ...).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
