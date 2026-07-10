"""Runtime settings for the Field Mapping service.

Prompt templates, model IDs, temperatures, and knowledge sources are runtime
configuration here — not per-request inputs (§4).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env to the service package root so it loads regardless of CWD
# (services are run from the repo root). Same fix as PRs #50/#56.
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FIELD_MAPPING_", env_file=_ENV_FILE, extra="ignore"
    )

    # LLM adapter mode: "replay" (deterministic fixtures) or "bedrock" (live).
    mode: str = "replay"
    # Bedrock invocation (design §9, ADR-0010) — used only in "bedrock" mode.
    # Invoke via the inference-profile id; the bare foundation-model id fails on-demand.
    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    aws_region: str = "us-east-1"
    max_tokens: int = 4096
    # Directory for stored mapping / synthesis-request / invocation-log artifacts.
    artifact_dir: str = "artifact-output/field-mapping"
    # Reuse a previously stored mapping artifact instead of regenerating (§13).
    reuse_stored_mapping_artifacts: bool = False
    # Repair-retry mode (§12) — off by default; not implemented yet.
    repair_retry_enabled: bool = False
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
