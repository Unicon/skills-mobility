"""Deterministic replay adapter.

Returns a committed, hand-authored canonical selection for the request instead of
calling a live model — so routine tests and local runs need no Bedrock access
(ADR-0013, FR-DT-30). It implements the same LLMAdapter protocol as the Bedrock
adapter (FR-DT-31). Fixtures are keyed by event_type; a ``default.json`` fixture
provides the Phase 1 behaviour (always select learncard_issuer + learncard_wallet,
FR-DT-35).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import SelectionGeneration, SelectionRequest

_DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _DEFAULT_FIXTURES_DIR

    def select(
        self, request: SelectionRequest, *, catalog: list[dict[str, Any]]
    ) -> SelectionGeneration:
        # Try event_type-specific fixture first, then fall back to default.
        path = self._dir / f"{request.event_type}.json"
        if not path.exists():
            path = self._dir / "default.json"
        raw: dict[str, Any] = json.loads(path.read_text())
        return SelectionGeneration(**raw)
