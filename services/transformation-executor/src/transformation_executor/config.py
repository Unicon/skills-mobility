"""Settings for the Transformation Executor.

Configuration comes from env vars (prefix ``TRANSFORMATION_EXECUTOR_``). In local
development a ``.env`` file at the service package root is loaded automatically.
In containers env vars come from the compose ``environment:`` block and the file
path doesn't exist — that is harmlessly ignored.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/transformation-executor/), not a
# bare ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) would silently ignore a service-dir .env.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRANSFORMATION_EXECUTOR_", env_file=_ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8160 — clear of Consul's 8300 and the other POC services.
    port: int = 8160

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
