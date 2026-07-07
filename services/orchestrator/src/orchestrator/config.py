"""Settings for the Orchestrator."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")

    # Local HTTP port. 8400 (not 8300 — that's Consul's default RPC port and
    # conflicts for anyone running Consul/Docker Desktop). Override: ORCHESTRATOR_PORT.
    port: int = 8400
    # Execution-state store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "orchestrator.db"
    # Issuer identity stamped into the stubbed OBv3 credential.
    issuer_id: str = "did:web:poc.skills-mobility.example"
    # Shared LearnCard delivery config (resolver + router), so it carries the
    # LEARNCARD_ prefix rather than ORCHESTRATOR_ (per #25 design §4).
    delivery_config_ref: str = Field(
        default="phase1-learncard-default", validation_alias="LEARNCARD_DELIVERY_CONFIG_REF"
    )
    # When set, each seam calls the real service over HTTP; else the Phase-1 stub.
    context_builder_url: str | None = None
    profile_resolver_url: str | None = None  # #51 Profile Resolver
    delivery_router_url: str | None = None  # #56 Delivery Router
    # Reusable delivery-phase plan lookup, off by default (FR-OR-28); toggle at runtime.
    reusable_plan_lookup_enabled: bool = False
    # Root log level for the service entrypoint (INFO, DEBUG, WARNING, ...).
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
