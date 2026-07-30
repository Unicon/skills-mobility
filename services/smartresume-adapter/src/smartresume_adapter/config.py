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

    # SmartResume base URL — no hard-coded default (FR-SR-13); must be set
    # explicitly. Expected value is the Mock SmartResume in all current
    # environments (local: http://localhost:8930; AWS: the deployed mock's URL).
    api_url: str

    # OAuth2 client_credentials — resolved from env, kept out of source (FR-SR-11).
    # Must match the Mock SmartResume's configured pair (demo: mock-client-id /
    # mock-access-key), supplied via .env / .env.example.
    client_id: str = ""
    access_key: str = ""


@lru_cache
def get_settings() -> Settings:
    # api_url is required (FR-SR-13) and supplied via env at runtime; mypy can't
    # see the env source, so the "missing arg" it infers here is expected.
    return Settings()  # type: ignore[call-arg]
