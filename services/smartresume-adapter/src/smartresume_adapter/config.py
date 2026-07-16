"""Settings for the SmartResume Adapter.

Service settings + the SmartResume vendor credentials live here (prefix
``SMARTRESUME_ADAPTER_``). ``ClientID`` and ``AccessKey`` are resolved from env
at runtime and never committed (FR-SR-11).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The service's own .env, anchored to the package root (services/smartresume-adapter/)
# so it loads regardless of the process CWD. A bare env_file=".env" resolves against
# CWD, so running from the repo root (the documented way) silently ignores it. In
# containers this path doesn't exist and env comes from compose `environment:`.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SMARTRESUME_ADAPTER_", env_file=ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8920 — outside Consul's reserved range (8300-8302, 8500,
    # 8600) and clear of the other POC services (mock-lms 8000, orchestrator 8400,
    # delivery-router 8800, learncard-wallet-adapter 8900, learncard-issuer 8910).
    port: int = 8920

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"

    # SmartResume base URL. Staging by default; point at the Mock SmartResume
    # (http://localhost:8930) locally or prod (https://my.smartresume.com) via env.
    api_url: str = "https://mystage.smartresume.com"

    # OAuth2 client_credentials — vendor secrets, resolved from env (FR-SR-11).
    client_id: str = ""
    access_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
