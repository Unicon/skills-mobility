"""Deterministic replay adapter.

Returns a committed, hand-authored canonical model output for the request instead
of calling a live model — so routine tests and local runs need no Bedrock access
(ADR-0013). It implements the same LLMAdapter protocol as the future Bedrock
adapter (FR-FM-31/32). The fixtures double as seeds for the ADR-0013 evaluation
corpus; once the Bedrock adapter lands, real captured outputs replace these.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_store import stable_key
from .contracts import MappingGeneration, MappingRequest

_DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"


class ReplayFixtureNotFoundError(Exception):
    """No committed replay fixture matches the request key."""


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _DEFAULT_FIXTURES_DIR

    def generate(
        self, request: MappingRequest, *, target_schema: dict[str, Any]
    ) -> MappingGeneration:
        key = stable_key(
            source_system=request.source_system,
            fetch_profile_id=request.fetch_profile_id,
            transformation_type=request.transformation_type,
            delivery_target=request.delivery_target,
        )
        path = self._dir / f"{key}.json"
        if not path.exists():
            raise ReplayFixtureNotFoundError(f"no replay fixture for {key}")
        return MappingGeneration(**json.loads(path.read_text()))
