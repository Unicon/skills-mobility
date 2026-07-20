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
from .contracts import LlmCallMeta, MappingGeneration, MappingRequest
from .prompt_builder import build_user_message, system_prompt

_DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"


class ReplayFixtureNotFoundError(Exception):
    """No committed replay fixture matches the request key."""


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _DEFAULT_FIXTURES_DIR

    def generate(
        self,
        request: MappingRequest,
        *,
        target_schema: dict[str, Any],
        source_catalogs: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[MappingGeneration, LlmCallMeta]:
        key = stable_key(
            source_system=request.source_system,
            fetch_profile_id=request.fetch_profile_id,
            transformation_type=request.transformation_type,
            delivery_target=request.delivery_target,
        )
        path = self._dir / f"{key}.json"
        if not path.exists():
            raise ReplayFixtureNotFoundError(f"no replay fixture for {key}")
        # Replay makes no live call, but the prompt is deterministic — capture it so
        # the invocation log still shows exactly what a live model would receive.
        # source_catalogs accepted but not used by replay (no live model call).
        meta = LlmCallMeta(
            provider="replay",
            model_id="replay",
            temperature=0.0,
            system_prompt=system_prompt(),
            user_prompt=build_user_message(request, target_schema, source_catalogs),
            prompt_template_version="replay",
        )
        return MappingGeneration(**json.loads(path.read_text())), meta
