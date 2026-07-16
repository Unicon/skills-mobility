"""Deterministic replay adapter.

Returns a committed, hand-authored canonical synthesis for the request instead of
calling a live model — so routine tests and local runs need no Bedrock access
(ADR-0013, FR-FS-27). It implements the same LLMAdapter protocol as the Bedrock
adapter (FR-FS-28). Fixtures are keyed by ``transformation_type``; a ``default.json``
fixture provides fallback coverage.

Coverage guarantee: for any requested ``placeholder_id`` that the fixture doesn't
cover, the adapter synthesises a deterministic stand-in value derived from the
brief's instruction or target_path. This ensures the coverage gate always passes
in replay mode even for unseen scenarios.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .contracts import LlmCallMeta, SynthesisBrief, SynthesisGeneration, SynthesisRequest
from .prompt_builder import build_user_message, system_prompt

_DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _DEFAULT_FIXTURES_DIR

    def generate(
        self, request: SynthesisRequest, *, briefs: list[SynthesisBrief]
    ) -> tuple[SynthesisGeneration, LlmCallMeta]:
        # Try transformation_type-specific fixture first, then fall back to default.
        path = self._dir / f"{request.transformation_type}.json"
        if not path.exists():
            path = self._dir / "default.json"
        raw: dict[str, Any] = json.loads(path.read_text())

        raw_values = raw.get("values") or {}
        fixture_values: dict[str, str] = {
            k: str(v) for k, v in raw_values.items() if isinstance(raw_values, dict)
        }
        raw_confidence = raw.get("confidence")
        confidence: float | None = float(raw_confidence) if raw_confidence is not None else None
        raw_rationale = raw.get("rationale")
        rationale: str | None = str(raw_rationale) if raw_rationale is not None else None

        # Build a coverage-complete values map for the exact requested placeholder_ids.
        # Any placeholder not in the fixture gets a deterministic stand-in so the
        # coverage gate always passes in replay (design: coverage-complete guarantee).
        requested_values: dict[str, str] = {}
        for brief in briefs:
            pid = brief.placeholder_id
            if pid in fixture_values:
                requested_values[pid] = fixture_values[pid]
            else:
                requested_values[pid] = _deterministic_standin(brief)

        # Replay makes no live call, but the prompt is deterministic — capture it so
        # the invocation log still shows exactly what a live model would receive.
        meta = LlmCallMeta(
            provider="replay",
            model_id="replay",
            temperature=0.0,
            system_prompt=system_prompt(),
            user_prompt=build_user_message(request, briefs),
        )
        generation = SynthesisGeneration(
            values=requested_values, confidence=confidence, rationale=rationale
        )
        return generation, meta


def _deterministic_standin(brief: SynthesisBrief) -> str:
    """Produce a deterministic stand-in value for an uncovered placeholder.

    Derived from the brief's instruction and target_path so it is stable across
    runs and clearly synthetic (not a plausible hallucination).
    """
    seed = f"{brief.placeholder_id}:{brief.target_path}:{brief.instruction}"
    digest = hashlib.sha1(seed.encode()).hexdigest()[:8]
    return f"[replay:{brief.placeholder_id}:{digest}]"
