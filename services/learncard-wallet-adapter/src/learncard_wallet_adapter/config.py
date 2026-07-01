"""Settings for the LearnCard Wallet Adapter.

Only service-level settings live here (prefix ``LEARNCARD_WALLET_ADAPTER_``).
The LearnCloud Network API base URL + pre-minted bearer come from the shared
``LearnCardSettings`` (prefix ``LEARNCARD_``, in libs/learncard-api).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEARNCARD_WALLET_ADAPTER_")

    # Local HTTP port. 8600 — clear of Consul's 8300 and the other POC services.
    port: int = 8600

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"

    # Recipient-scoped read token (credentials:read) for the delivered-credential
    # read-back (#53). Distinct from the sender token (LEARNCARD_API_TOKEN) used to
    # deliver; carries the LEARNCARD_ prefix (shared with the demo wallet), so it is
    # read via an explicit alias rather than the LEARNCARD_WALLET_ADAPTER_ prefix.
    recipient_api_token: str = Field(
        default="", validation_alias="LEARNCARD_RECIPIENT_API_TOKEN"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
