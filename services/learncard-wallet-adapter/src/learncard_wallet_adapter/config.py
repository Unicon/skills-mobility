"""Settings for the LearnCard Wallet Adapter.

Only service-level settings live here (prefix ``LEARNCARD_WALLET_ADAPTER_``).
The LearnCloud Network API base URL + pre-minted bearer come from the shared
``LearnCardSettings`` (prefix ``LEARNCARD_``, in libs/learncard-api).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The service's own .env, anchored to the package root (services/learncard-wallet-adapter/)
# so it loads regardless of the process CWD. A bare env_file=".env" resolves against
# CWD, so running from the repo root (the documented way) silently ignored it. The same
# path is passed to LearnCardSettings in app.py so the LEARNCARD_ token loads too. In
# containers this path doesn't exist and env comes from compose `environment:`.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEARNCARD_WALLET_ADAPTER_", env_file=ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8900 — outside Consul's reserved range (8300-8302, 8500,
    # 8600) and clear of the other POC services (mock-lms 8000, orchestrator 8400,
    # delivery-router 8800).
    port: int = 8900

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
