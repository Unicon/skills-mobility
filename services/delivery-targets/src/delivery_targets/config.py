"""Runtime settings for the Delivery Targets service.

Prompt templates, model IDs, temperatures, and catalog paths are runtime
configuration here — not per-request inputs (design §6).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env to the service package root so it loads regardless of CWD.
# src/delivery_targets/config.py:
#   parents[0] = src/delivery_targets
#   parents[1] = src
#   parents[2] = delivery-targets  (service root, where .env lives)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DELIVERY_TARGETS_", env_file=_ENV_FILE, extra="ignore"
    )

    # LLM adapter mode: "replay" (deterministic fixtures) or "bedrock" (live).
    mode: Literal["replay", "bedrock"] = "replay"
    # Directory for stored selection / invocation-log artifacts.
    artifact_dir: str = "artifact-output/delivery-targets"
    # Bedrock model id (inference-profile qualified).
    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # AWS region for Bedrock.
    aws_region: str = "us-east-1"
    # Maximum tokens for Bedrock generation.
    max_tokens: int = 1024
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
