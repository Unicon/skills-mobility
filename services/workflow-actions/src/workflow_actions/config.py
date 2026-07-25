"""Runtime settings for the Workflow Actions service.

Prompt templates, model IDs, temperatures, and artifact paths are runtime
configuration — not per-request inputs (design §6).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor the .env to the service package root so it loads regardless of CWD.
# src/workflow_actions/config.py:
#   parents[0] = src/workflow_actions
#   parents[1] = src
#   parents[2] = workflow-actions  (service root, where .env lives)
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WORKFLOW_ACTIONS_", env_file=_ENV_FILE, extra="ignore"
    )

    # LLM adapter mode: "replay" (deterministic fixtures) or "bedrock" (live).
    mode: str = "replay"
    # Directory for stored plan / invocation-log artifacts.
    artifact_dir: str = "artifact-output/workflow-actions"
    # Bedrock model id (inference-profile qualified).
    model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # AWS region for Bedrock.
    aws_region: str = "us-east-1"
    # Maximum tokens for Bedrock generation.
    max_tokens: int = 2048
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
