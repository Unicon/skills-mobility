"""Deterministic replay adapter.

Returns a committed, hand-authored canonical selection for the request instead of
calling a live model — so routine tests and local runs need no Bedrock access
(ADR-0013, FR-DT-30). It implements the same LLMAdapter protocol as the Bedrock
adapter (FR-DT-31). Fixtures are keyed by **course subject** — the actual routing
bifurcation (design §3/§5: Accounting ``ACCY-*`` vs Finance ``FINC-*``), not event
type. The subject is derived from the first ``course_id`` found in
``learner_context`` (the Orchestrator passes the Context Builder bundle, where the
id sits nested under ``source_data``; tests pass it flat). A ``default.json``
fixture provides the Phase 1 fallback when no subject is resolvable (FR-DT-33/35).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .contracts import LlmCallMeta, SelectionGeneration, SelectionRequest
from .prompt_builder import build_user_message, system_prompt

logger = logging.getLogger(__name__)

_DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"


def _find_course_id(node: Any) -> str | None:
    """Depth-first search for the first string-valued ``course_id`` key."""
    if isinstance(node, dict):
        value = node.get("course_id")
        if isinstance(value, str) and value:
            return value
        for child in node.values():
            found = _find_course_id(child)
            if found is not None:
                return found
    elif isinstance(node, list):
        for child in node:
            found = _find_course_id(child)
            if found is not None:
                return found
    return None


def resolve_subject(learner_context: dict[str, Any]) -> str | None:
    """Course subject from the context's course id: ``ACCY-111`` -> ``accy``."""
    course_id = _find_course_id(learner_context)
    if course_id is None or "-" not in course_id:
        return None
    return course_id.split("-", 1)[0].lower()


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _DEFAULT_FIXTURES_DIR

    def select(
        self, request: SelectionRequest, *, catalog: list[dict[str, Any]]
    ) -> tuple[SelectionGeneration, LlmCallMeta]:
        # Subject-specific fixture first (accy.json / finc.json), else default.
        subject = resolve_subject(request.learner_context)
        path = self._dir / f"{subject}.json" if subject else None
        if path is None or not path.exists():
            logger.info(
                "replay fixture fallback: execution_id=%s subject=%s -> default.json",
                request.execution_id, subject,
            )
            path = self._dir / "default.json"
        else:
            logger.info(
                "replay fixture selected: execution_id=%s subject=%s -> %s",
                request.execution_id, subject, path.name,
            )
        raw: dict[str, Any] = json.loads(path.read_text())
        # Replay makes no live call, but the prompt is deterministic — capture it so
        # the invocation log still shows exactly what a live model would receive.
        meta = LlmCallMeta(
            provider="replay",
            model_id="replay",
            temperature=0.0,
            system_prompt=system_prompt(),
            user_prompt=build_user_message(request, catalog),
        )
        return SelectionGeneration(**raw), meta
