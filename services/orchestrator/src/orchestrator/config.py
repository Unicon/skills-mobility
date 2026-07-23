"""Settings for the Orchestrator."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Anchor .env to the service package root (services/orchestrator/), not a bare
# ".env": a relative env_file resolves against the process CWD, so running from
# the repo root (the documented way) silently ignored a service-dir .env. In
# containers this path doesn't exist and env comes from compose `environment:`.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORCHESTRATOR_", env_file=ENV_FILE, extra="ignore"
    )

    # Local HTTP port. 8400 (not 8300 — that's Consul's default RPC port and
    # conflicts for anyone running Consul/Docker Desktop). Override: ORCHESTRATOR_PORT.
    port: int = 8400
    # Execution-state store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "orchestrator.db"
    # When set, the execution store is DynamoDB instead of SQLite — required on
    # Lambda, whose per-instance /tmp can't be shared across invocations (the
    # Admin UI polls a possibly-different instance than the one that ran the
    # workflow). Names the single state table (ADR-0014 §9; infra #107 foundation).
    dynamo_table: str | None = None
    # Region for the DynamoDB client; None → boto3 default (AWS_REGION on Lambda).
    aws_region: str | None = None
    # Issuer identity stamped into the stubbed OBv3 credential.
    issuer_id: str = "did:web:poc.skills-mobility.example"
    # Shared LearnCard delivery config (resolver + router), so it carries the
    # LEARNCARD_ prefix rather than ORCHESTRATOR_ (per #25 design §4).
    delivery_config_ref: str = Field(
        default="phase1-learncard-default", validation_alias="LEARNCARD_DELIVERY_CONFIG_REF"
    )
    # Fixed pre-provisioned recipient wallet the POC resolves + delivers to
    # (ADR-0020). Its LearnCard handle == profileId; shared LearnCard config, so
    # LEARNCARD_-prefixed. Matches the demo tooling's DEMO_RECIPIENT_PROFILE_ID.
    demo_recipient_profile_id: str = Field(
        default="smi-demo-learner", validation_alias="LEARNCARD_DEMO_RECIPIENT_PROFILE_ID"
    )
    # When set, each seam calls the real service over HTTP; else the Phase-1 stub.
    context_builder_url: str | None = None
    profile_resolver_url: str | None = None  # #51 Profile Resolver
    delivery_router_url: str | None = None  # #56 Delivery Router
    # #27 Field Mapping service. When set, the mapping steps call it for real
    # (best-effort — the deterministic obv3 stand-in still produces the payload);
    # else the Phase-1 stub returns null refs.
    field_mapping_url: str | None = None
    # #27/ADR-0007 LLM Decision Service planner seams. When set, the planner path
    # calls these for real (best-effort — a failure falls back to the deterministic
    # gate/targets/plan stubs); else the stubs are used.
    delivery_targets_url: str | None = None  # #77 Delivery Targets
    workflow_actions_url: str | None = None  # #78 Workflow Actions (gate + plan)
    # Reusable delivery-phase plan lookup, off by default (FR-OR-28); toggle at runtime.
    reusable_plan_lookup_enabled: bool = False
    # Root log level for the service entrypoint (INFO, DEBUG, WARNING, ...).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
