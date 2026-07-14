"""Build Bedrock prompts for each stage (design §6 / §12).

Static rules live in version-controlled templates (prompt_templates/); the
per-request data becomes the user message. Prompt changes are reviewable as
template edits.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import GateRequest, PlanRequest

GATE_PROMPT_VERSION = "pre_target_gate.v1"
PLAN_PROMPT_VERSION = "delivery_phase_plan.v1"

_GATE_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "prompt_templates" / "pre_target_gate.v1.md"
)
_PLAN_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "prompt_templates" / "delivery_phase_plan.v1.md"
)


def gate_system_prompt(gating_prose: str) -> str:
    """Render the gate system prompt, inserting the administrator-authored prose."""
    template = _GATE_TEMPLATE_PATH.read_text()
    return template.replace("{gating_policy_prose}", gating_prose)


def build_gate_user_message(request: GateRequest) -> str:
    """Assemble the gate user message: event type + event envelope + context bundle."""
    task = {
        "event_type": request.event_type,
        "event_id": request.event_id,
        "execution_id": request.execution_id,
    }
    parts = [
        "Evaluate whether this workflow event should proceed to delivery-target selection.",
        "",
        f"## Event metadata\n```json\n{json.dumps(task, indent=2)}\n```",
        "",
        f"## Event\n```json\n{json.dumps(request.event, indent=2)}\n```",
        "",
        f"## Context bundle\n```json\n{json.dumps(request.context_bundle, indent=2)}\n```",
    ]
    if request.policy_context:
        parts += [
            "",
            f"## Policy context\n```json\n{json.dumps(request.policy_context, indent=2)}\n```",
        ]
    return "\n".join(parts)


def plan_system_prompt(registry_view: list[dict[str, str]]) -> str:
    """Render the plan system prompt, inserting the action-registry view."""
    registry_text = json.dumps(registry_view, indent=2)
    template = _PLAN_TEMPLATE_PATH.read_text()
    return template.replace("{registry_view}", registry_text)


def build_plan_user_message(request: PlanRequest) -> str:
    """Assemble the plan user message: targets, event, context."""
    task: dict[str, Any] = {
        "event_type": request.event_type,
        "source_system": request.source_system,
        "event_id": request.event_id,
        "execution_id": request.execution_id,
        "selected_targets": request.selected_targets,
    }
    return "\n".join(
        [
            "Generate the delivery-phase plan for the selected targets.",
            "",
            f"## Request\n```json\n{json.dumps(task, indent=2)}\n```",
            "",
            f"## Event\n```json\n{json.dumps(request.event, indent=2)}\n```",
            "",
            f"## Context bundle\n```json\n{json.dumps(request.context_bundle, indent=2)}\n```",
        ]
    )
