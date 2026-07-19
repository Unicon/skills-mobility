"""Build the Bedrock prompt for a mapping request (design §7).

The static rules live in a version-controlled template (``prompt_templates/``) and
become the system prompt; the per-request data (transformation context, target
schema, and the supplied source payloads) becomes the user message. Prompt changes
are reviewable as template edits, and the template version is recorded for the
invocation log.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import MappingRequest

PROMPT_TEMPLATE_VERSION = "field_mapping.v1"
_TEMPLATE_PATH = Path(__file__).resolve().parent / "prompt_templates" / "field_mapping.v1.md"


def system_prompt() -> str:
    return _TEMPLATE_PATH.read_text()


def build_user_message(
    request: MappingRequest,
    target_schema: dict[str, Any],
    source_catalogs: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Assemble the user message: the mapping task, the target schema, the
    supplied source payloads (already screened by the caller), and optionally
    the resolved source-field catalog excerpts (design §7)."""
    task = {
        "transformation_type": str(request.transformation_type),
        "delivery_target": str(request.delivery_target) if request.delivery_target else None,
        "synthesis_allowed": request.synthesis_allowed,
    }
    parts = [
        "Map the supplied source payloads to the target schema.\n\n"
        f"## Task\n```json\n{json.dumps(task, indent=2)}\n```\n\n"
        f"## Target schema\n```json\n{json.dumps(target_schema, indent=2)}\n```\n\n"
        f"## Source payloads\n```json\n{json.dumps(request.source_payloads, indent=2)}\n```\n"
    ]
    if source_catalogs:
        parts.append(
            f"\n## Source field catalogs\n```json\n{json.dumps(source_catalogs, indent=2)}\n```\n"
        )
    return "".join(parts)
