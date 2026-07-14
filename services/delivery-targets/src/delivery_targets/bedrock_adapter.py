"""Bedrock provider adapter (design §8, ADR-0010).

A thin adapter over Bedrock's Converse API. It screens the learner context for
prompt injection (FR-DT-24), builds the prompt, and forces a schema-constrained
structured response via tool use, at temperature 0 for a stable routing decision.
The configured ``model_id`` should be an inference-profile id (e.g.
``us.anthropic.claude-haiku-4-5-20251001-v1:0``). Credentials come from the normal
AWS SDK chain (FR-DT-28); no API-key layer.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3

from .contracts import SelectionGeneration, SelectionRequest
from .prompt_builder import build_user_message, system_prompt
from .screen import screen_for_injection

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_selection"


class BedrockResponseError(Exception):
    """The Converse response did not contain the expected structured tool output."""


class BedrockAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_tokens: int = 1024,
        client: Any = None,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._max_tokens = max_tokens
        self._client = client  # lazily created so replay-mode never needs AWS

    def _bedrock(self) -> Any:
        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    def select(
        self, request: SelectionRequest, *, catalog: list[dict[str, Any]]
    ) -> SelectionGeneration:
        # FR-DT-24: screen free-text before it reaches the prompt.
        findings = screen_for_injection(request.learner_context)
        if findings:
            logger.warning(
                "prompt-injection screen flagged learner context values: %s",
                [f.path for f in findings],
            )

        tool_schema = SelectionGeneration.model_json_schema()
        user_text = build_user_message(request, catalog)
        response = self._bedrock().converse(
            modelId=self._model_id,
            system=[{"text": system_prompt()}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": 0.0, "maxTokens": self._max_tokens},
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": _TOOL_NAME,
                            "description": "Emit the selected delivery targets.",
                            "inputSchema": {"json": tool_schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": _TOOL_NAME}},
            },
        )
        return SelectionGeneration(**_extract_tool_input(response))


def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
    content = response["output"]["message"]["content"]
    for block in content:
        if "toolUse" in block:
            tool_input: dict[str, Any] = block["toolUse"]["input"]
            return tool_input
    raise BedrockResponseError("Converse response contained no toolUse block")
