"""Settings for the LearnCard Profile Resolver.

Service-level settings (prefix ``LEARNCARD_PROFILE_RESOLVER_``). The LearnCloud
Network API base URL + pre-minted bearer come from the shared ``LearnCardSettings``
(prefix ``LEARNCARD_``, in libs/learncard-api).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEARNCARD_PROFILE_RESOLVER_")

    # Local HTTP port. 8700 — clear of Consul's 8300 and the other POC services.
    port: int = 8700

    # Local mapping store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "learncard-profile-resolver.db"

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
