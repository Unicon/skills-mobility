"""Build the Bedrock prompt for a synthesis request (design §7).

The static role and grounding rules live in a version-controlled template
(``prompt_templates/``) and become the system prompt; the per-request data
(transformation_type and per-brief placeholder_id, target_path, instruction,
and source_payloads) becomes the user message. Prompt changes are reviewable as
template edits, and the template version is recorded in the invocation log.
"""

from __future__ import annotations

import json
from pathlib import Path

from .contracts import SynthesisBrief, SynthesisRequest

PROMPT_VERSION = "field_synthesis.v1"
_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "prompt_templates" / "field_synthesis.v1.md"
)


def system_prompt() -> str:
    return _TEMPLATE_PATH.read_text()


def build_user_message(request: SynthesisRequest, briefs: list[SynthesisBrief]) -> str:
    """Assemble the user message: the transformation context, then each brief's
    placeholder_id, target_path, instruction, and source_payloads as delimited JSON."""
    brief_payloads = [
        {
            "placeholder_id": b.placeholder_id,
            "target_path": b.target_path,
            "instruction": b.instruction,
            "source_payloads": b.source_payloads,
        }
        for b in briefs
    ]
    task = {
        "transformation_type": request.transformation_type,
        "briefs": brief_payloads,
    }
    return (
        "Generate human-facing text for the following credential field placeholders.\n\n"
        f"## Synthesis task\n```json\n{json.dumps(task, indent=2)}\n```\n"
    )
