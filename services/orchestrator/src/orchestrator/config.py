"""Settings for the Orchestrator."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")

    # Execution-state store (ADR-0014: SQLite locally). ":memory:" for ephemeral runs.
    db_path: str = "orchestrator.db"
    # Issuer identity stamped into the stubbed OBv3 credential.
    issuer_id: str = "did:web:poc.skills-mobility.example"
    # Delivery configuration handle attached to the execution context (design §4).
    delivery_config_ref: str = "phase1-learncard-default"
    # When set, each seam calls the real service over HTTP; else the Phase-1 stub.
    context_builder_url: str | None = None
    profile_resolver_url: str | None = None  # #19 — unbuilt; HTTP client wires in later
    delivery_router_url: str | None = None  # #19 — unbuilt; HTTP client wires in later
    # Reusable delivery-phase plan lookup, off by default (FR-OR-28); toggle at runtime.
    reusable_plan_lookup_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
