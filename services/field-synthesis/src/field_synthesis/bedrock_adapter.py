"""Bedrock provider adapter (design §8, ADR-0010).

A thin adapter over Bedrock's Converse API. It screens each brief's source_payloads
for prompt injection (FR-FS-22), builds the prompt, and forces a schema-constrained
structured response via tool use at a low non-zero temperature appropriate for
natural-language generation (ADR-0010 design §16). The configured ``model_id``
should be an inference-profile id (e.g. ``us.anthropic.claude-haiku-4-5-20251001-v1:0``).
Credentials come from the normal AWS SDK chain (FR-FS-25); no API-key layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import boto3

from .contracts import LlmCallMeta, SynthesisBrief, SynthesisGeneration, SynthesisRequest
from .prompt_builder import build_user_message, system_prompt
from .screen import screen_briefs_for_injection

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_synthesis"
# Non-zero temperature: generative text task (design §16, ADR-0010), not routing.
_TEMPERATURE = 0.3


class BedrockResponseError(Exception):
    """The Converse response did not contain the expected structured tool output."""


class BedrockAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_tokens: int = 2048,
        temperature: float = _TEMPERATURE,
        client: Any = None,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = client  # lazily created so replay-mode never needs AWS

    def _bedrock(self) -> Any:
        if self._client is None:
            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    def generate(
        self, request: SynthesisRequest, *, briefs: list[SynthesisBrief]
    ) -> tuple[SynthesisGeneration, LlmCallMeta]:
        # FR-FS-22: screen source_payloads in each brief before they reach the prompt.
        brief_dicts = [b.model_dump() for b in briefs]
        findings = screen_briefs_for_injection(brief_dicts)
        if findings:
            logger.warning(
                "prompt-injection screen flagged source_payload values: %s",
                [f.path for f in findings],
            )

        tool_schema = SynthesisGeneration.model_json_schema()
        sys_text = system_prompt()
        user_text = build_user_message(request, briefs)
        started = time.perf_counter()
        response = self._bedrock().converse(
            modelId=self._model_id,
            system=[{"text": sys_text}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": self._temperature, "maxTokens": self._max_tokens},
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": _TOOL_NAME,
                            "description": "Emit the generated field synthesis values.",
                            "inputSchema": {"json": tool_schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": _TOOL_NAME}},
            },
        )
        latency_ms = (time.perf_counter() - started) * 1000.0
        usage = response.get("usage", {})
        meta = LlmCallMeta(
            provider="bedrock",
            model_id=self._model_id,
            temperature=self._temperature,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            latency_ms=latency_ms,
            system_prompt=sys_text,
            user_prompt=user_text,
        )
        return SynthesisGeneration(**_extract_tool_input(response)), meta


def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
    content = response["output"]["message"]["content"]
    for block in content:
        if "toolUse" in block:
            tool_input: dict[str, Any] = block["toolUse"]["input"]
            return tool_input
    raise BedrockResponseError("Converse response contained no toolUse block")
