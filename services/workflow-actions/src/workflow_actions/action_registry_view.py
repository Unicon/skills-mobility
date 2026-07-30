"""Load and expose the action registry (design §12 / FR-WA-9a/9b).

The service owns its action registry directly; the Orchestrator does not supply
it as an input. This module loads the committed JSON file and provides:
  - the set of valid (action_id, type) pairs for validation
  - the prompt-time projection (action_id + description) for plan prompts
  - the gating policy prose for gate prompts
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REGISTRY_PATH = Path(__file__).resolve().parent / "catalogs" / "action_registry.json"


def _load() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_REGISTRY_PATH.read_text())
    return data


def valid_action_pairs() -> set[tuple[str, str]]:
    """Return the set of valid (action_id, type) tuples from the registry."""
    registry = _load()
    return {(entry["action_id"], entry["type"]) for entry in registry["actions"]}


def prompt_projection() -> list[dict[str, str]]:
    """Return the prompt-time projection: list of {action_id, description} dicts."""
    registry = _load()
    return [
        {"action_id": entry["action_id"], "description": entry["description"]}
        for entry in registry["actions"]
    ]


def gating_prose() -> str:
    """Return the administrator-authored gating policy prose (FR-WA-3a)."""
    registry = _load()
    return str(registry["gating_policy_prose"])
