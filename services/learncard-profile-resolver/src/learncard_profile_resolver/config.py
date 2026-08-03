"""Settings for the LearnCard Profile Resolver.

Service-level settings (prefix ``LEARNCARD_PROFILE_RESOLVER_``). The LearnCloud
Network API base URL + pre-minted bearer come from the shared ``LearnCardSettings``
(prefix ``LEARNCARD_``, in libs/learncard-api).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The service's own .env, anchored to the package root (services/learncard-profile-resolver/)
# so it loads regardless of the process CWD. A bare env_file=".env" resolves against CWD,
# so running from the repo root (the documented way) silently ignored it. The same path is
# passed to LearnCardSettings in app.py so the LEARNCARD_ token loads too. In containers this
# path doesn't exist and env comes from compose `environment:`.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LEARNCARD_PROFILE_RESOLVER_", env_file=ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8700 — clear of Consul's 8300 and the other POC services.
    port: int = 8700

    # Local mapping store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "learncard-profile-resolver.db"

    # DynamoDB mapping store (ADR-0014: Lambda). When set, it replaces the SQLite
    # store — same selection seam as the orchestrator's ORCHESTRATOR_DYNAMO_TABLE.
    dynamo_table: str | None = None
    aws_region: str | None = None

    # Root log level for the service entrypoint (e.g. INFO, DEBUG, WARNING).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
