"""Deterministic replay adapter (design §12 / ADR-0013).

Returns committed, hand-authored canonical gate decisions and plans instead of
calling a live model — so routine tests and local runs need no Bedrock access.
Implements the same LLMAdapter protocol as the Bedrock adapter.

Gate fixtures are keyed by event_type; unsupported event types get the
terminate fixture. Plan fixtures are keyed by the selected final delivery
target(s): wallet selections (and the Phase-1 default) get the wallet fixture,
SmartResume selections get the SmartResume fixture, and both together get the
combined fixture — all three share the credential-template + issuer + issuance
prefix (ADR-0017).
"""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import (
    GateGeneration,
    GateRequest,
    LlmCallMeta,
    LlmPlanOutput,
    PlanGeneration,
    PlanRequest,
    plan_generation_from_llm_output,
)
from .prompt_builder import (
    build_gate_user_message,
    build_plan_user_message,
    gate_system_prompt,
    plan_system_prompt,
)

_FIXTURES_DIR = Path(__file__).resolve().parent / "replay_fixtures"

_SUPPORTED_EVENT_TYPES = frozenset(["skill_mastered", "course_completed"])


def _replay_meta(system_prompt: str, user_prompt: str) -> LlmCallMeta:
    # Replay makes no live call, but the prompt is deterministic — capture it so
    # the invocation log still shows exactly what a live model would receive.
    return LlmCallMeta(
        provider="replay",
        model_id="replay",
        temperature=0.0,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


class ReplayAdapter:
    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self._dir = fixtures_dir or _FIXTURES_DIR

    def gate(
        self, request: GateRequest, *, gating_prose: str
    ) -> tuple[GateGeneration, LlmCallMeta]:
        # Try event_type-specific fixture, fall back to unsupported.
        if request.event_type in _SUPPORTED_EVENT_TYPES:
            fixture_name = f"gate_{request.event_type}.json"
        else:
            fixture_name = "gate_unsupported.json"
        raw = json.loads((self._dir / fixture_name).read_text())
        meta = _replay_meta(gate_system_prompt(gating_prose), build_gate_user_message(request))
        return GateGeneration(**raw), meta

    def plan(
        self, request: PlanRequest, *, registry_view: list[dict[str, str]]
    ) -> tuple[PlanGeneration, LlmCallMeta]:
        # The fixture is keyed by the selected final delivery target(s) — the shared
        # prefix (credential template -> issuer payload -> issuance) always runs
        # (LearnCard is the only issuer), the targets decide only the delivery
        # branch(es). Fixtures are the lean LLM shape (ordered action_ids);
        # applicability + bindings are derived, not fixtured.
        has_wallet = "learncard_wallet" in request.selected_targets
        has_smartresume = "smart_resume" in request.selected_targets
        if has_smartresume and has_wallet:
            fixture_name = "plan_learncard_and_smartresume.json"
        elif has_smartresume:
            fixture_name = "plan_smartresume.json"
        else:
            # Wallet selection — or no known final target (Phase-1 default).
            fixture_name = "plan_learncard_wallet.json"
        raw = json.loads((self._dir / fixture_name).read_text())
        llm_out = LlmPlanOutput(**raw)
        meta = _replay_meta(plan_system_prompt(registry_view), build_plan_user_message(request))
        return plan_generation_from_llm_output(llm_out, request), meta
