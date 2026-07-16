"""Runtime settings for the Field Synthesis service.

Prompt templates, model IDs, temperatures, and other LLM runtime settings are
service configuration here — not per-request inputs (design §6). Temperature is
intentionally non-zero for this generative service (ADR-0010, design §16).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env to the service package root so it loads regardless of CWD.
# src/field_synthesis/config.py:
#   parents[0] = src/field_synthesis
#   parents[1] = src
#   parents[2] = field-synthesis  (service root, where .env lives)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FIELD_SYNTHESIS_", env_file=_ENV_FILE, extra="ignore"
    )

    # LLM adapter mode: "replay" (deterministic fixtures) or "bedrock" (live).
    mode: str = "replay"
    # Directory for stored synthesis result / invocation-log artifacts.
    artifact_dir: str = "artifact-output/field-synthesis"
    # Bedrock model id (inference-profile qualified).
    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # AWS region for Bedrock.
    aws_region: str = "us-east-1"
    # Maximum tokens for Bedrock generation (higher than siblings — all placeholders in one call).
    max_tokens: int = 2048
    # Low non-zero temperature: appropriate for generative text, not structural/routing decisions.
    temperature: float = 0.3
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
