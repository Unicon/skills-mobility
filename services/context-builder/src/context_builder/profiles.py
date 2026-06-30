"""Fetch profiles (the Source Fetch Rules Store): versioned YAML recipes,
one per event type, that the engine executes deterministically.

A profile is `{id, event_type, version, steps[]}`. Each step's optional
`params` / `condition` / `select` / `for_each` are kept as plain config dicts;
the engine (`engine.py`) is the interpreter. Profiles ship in the package
(`fetch_profiles/`) and are loaded read-only at startup.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml
from pydantic import BaseModel


class Step(BaseModel):
    output_key: str
    endpoint: str
    params: dict[str, dict[str, Any]] = {}
    condition: dict[str, Any] | None = None
    select: dict[str, Any] | None = None
    for_each: dict[str, Any] | None = None


class FetchProfile(BaseModel):
    id: str
    event_type: str
    version: int
    steps: list[Step]


def load_profiles() -> dict[str, FetchProfile]:
    """Load every packaged ``fetch_profiles/*.yaml``, keyed by event type."""
    out: dict[str, FetchProfile] = {}
    profile_dir = files("context_builder.fetch_profiles")
    for entry in profile_dir.iterdir():
        if not entry.name.endswith(".yaml"):
            continue
        profile = FetchProfile.model_validate(yaml.safe_load(entry.read_text(encoding="utf-8")))
        out[profile.event_type] = profile
    return out
