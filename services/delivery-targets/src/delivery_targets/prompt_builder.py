"""Build the Bedrock prompt for a selection request (design §7).

The static rules live in a version-controlled template (``prompt_templates/``) and
become the system prompt; the per-request data (event type, source system, learner
context, and the resolved catalog) becomes the user message. Prompt changes are
reviewable as template edits, and the template version is recorded for the
invocation log.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import SelectionRequest

PROMPT_TEMPLATE_VERSION = "delivery_targets.v1"
_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "prompt_templates" / "delivery_targets.v1.md"
)


def system_prompt() -> str:
    return _TEMPLATE_PATH.read_text()


def build_user_message(
    request: SelectionRequest, catalog: list[dict[str, Any]]
) -> str:
    """Assemble the user message: the routing task, the catalog, and the learner
    context (already screened by the caller)."""
    task = {
        "event_type": request.event_type,
        "source_system": request.source_system,
    }
    return (
        "Select the appropriate delivery targets for this event.\n\n"
        f"## Event\n```json\n{json.dumps(task, indent=2)}\n```\n\n"
        f"## Available delivery targets\n```json\n{json.dumps(catalog, indent=2)}\n```\n\n"
        f"## Learner context\n```json\n{json.dumps(request.learner_context, indent=2)}\n```\n"
    )
