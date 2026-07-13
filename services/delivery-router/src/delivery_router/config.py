"""Settings for the Delivery Router.

For the POC there is a single delivery-config bundle: the adapter endpoint URLs
+ delivery mechanics come from env (prefix ``DELIVERY_ROUTER_``). The
``delivery_config_ref`` on each request is validated and passed through to the
adapter (so it resolves its own vendor credentials), but multi-bundle lookup by
ref is a later concern.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from delivery_router.schemas import AdapterKey

# Anchor .env to the service package root (services/delivery-router/), not a bare
# ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) silently ignored a service-dir .env and left
# the adapter URLs None. In containers this path doesn't exist and env comes from
# compose `environment:`, so it's harmlessly ignored there.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DELIVERY_ROUTER_", env_file=_ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8800 — clear of Consul's 8300 and the other POC services.
    port: int = 8800

    # Adapter endpoint base URLs (unset -> that action can't be dispatched).
    learncard_issuer_url: str | None = None
    learncard_wallet_url: str | None = None

    # Shared delivery mechanics (deterministic, config-driven).
    request_timeout: float = 30.0
    retry_limit: int = 1  # retries on transport errors, on top of the first try

    log_level: str = "INFO"

    def adapter_url(self, adapter_key: AdapterKey) -> str | None:
        return {
            AdapterKey.LEARNCARD_ISSUER: self.learncard_issuer_url,
            AdapterKey.LEARNCARD_WALLET: self.learncard_wallet_url,
        }[adapter_key]


@lru_cache
def get_settings() -> Settings:
    return Settings()
