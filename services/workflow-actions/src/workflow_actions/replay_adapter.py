"""Deterministic replay adapter (design §12 / ADR-0013).

Returns committed, hand-authored canonical gate decisions and plans instead of
calling a live model — so routine tests and local runs need no Bedrock access.
Implements the same LLMAdapter protocol as the Bedrock adapter.

Gate fixtures are keyed by event_type; unsupported event types get the
terminate fixture. Plan fixtures are keyed by target applicability; the
dual LearnCard fixture covers the Phase-1 happy path.
"""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import GateGeneration, GateRequest, PlanGeneration, PlanRequest

_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"

_SUPPORTED_EVENT_TYPES = frozenset(["skill_mastered", "course_completed"])


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _FIXTURES_DIR

    def gate(self, request: GateRequest, *, gating_prose: str) -> GateGeneration:
        # Try event_type-specific fixture, fall back to unsupported.
        if request.event_type in _SUPPORTED_EVENT_TYPES:
            fixture_name = f"gate_{request.event_type}.json"
        else:
            fixture_name = "gate_unsupported.json"
        raw = json.loads((self._dir / fixture_name).read_text())
        return GateGeneration(**raw)

    def plan(
        self, request: PlanRequest, *, registry_view: list[dict[str, str]]
    ) -> PlanGeneration:
        # Phase 1: the dual-LearnCard fixture covers the happy path.
        raw = json.loads((self._dir / "plan_learncard_dual.json").read_text())
        # Patch applicability to match the actual request.
        raw["applicability"] = {
            "event_type": request.event_type,
            "source_system": request.source_system,
            "selected_targets": list(request.selected_targets),
        }
        return PlanGeneration(**raw)
