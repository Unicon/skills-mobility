"""Bedrock provider adapter (design §9, ADR-0010).

A thin adapter over Bedrock's Converse API. It screens the source payloads for
prompt injection (FR-FM-27b), builds the prompt, and forces a schema-constrained
structured response via tool use, at temperature 0 for machine-executable output.
The bare foundation-model id is not invocable on-demand for these models — the
configured ``model_id`` should be an inference-profile id (e.g.
``us.anthropic.claude-haiku-4-5-20251001-v1:0``). Credentials come from the normal
AWS SDK chain (FR-FM-29); no API-key layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import boto3

from .contracts import LlmCallMeta, MappingGeneration, MappingRequest
from .prompt_builder import PROMPT_TEMPLATE_VERSION, build_user_message, system_prompt
from .screen import screen_for_injection

logger = logging.getLogger(__name__)

_TOOL_NAME = "emit_mapping"
_TEMPERATURE = 0.0


class BedrockResponseError(Exception):
    """The Converse response did not contain the expected structured tool output."""


class BedrockAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_tokens: int = 4096,
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

    def generate(
        self,
        request: MappingRequest,
        *,
        target_schema: dict[str, Any],
        source_catalogs: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[MappingGeneration, LlmCallMeta]:
        # FR-FM-27b: screen free-text before it reaches the prompt.
        findings = screen_for_injection(request.source_payloads)
        if findings:
            logger.warning(
                "prompt-injection screen flagged source payload values: %s",
                [f.path for f in findings],
            )

        tool_schema = MappingGeneration.model_json_schema()
        sys_text = system_prompt()
        user_text = build_user_message(request, target_schema, source_catalogs)
        started = time.perf_counter()
        response = self._bedrock().converse(
            modelId=self._model_id,
            system=[{"text": sys_text}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": _TEMPERATURE, "maxTokens": self._max_tokens},
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": _TOOL_NAME,
                            "description": "Emit the JSONata mapping and its metadata.",
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
            temperature=_TEMPERATURE,
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
            latency_ms=latency_ms,
            system_prompt=sys_text,
            user_prompt=user_text,
            injection_findings=[{"path": f.path, "snippet": f.snippet} for f in findings],
            prompt_template_version=PROMPT_TEMPLATE_VERSION,
        )
        try:
            generation = MappingGeneration(**_extract_tool_input(response))
        except Exception as exc:
            raise BedrockResponseError(
                f"Bedrock tool output did not match the expected schema: {exc}"
            ) from exc
        return generation, meta


def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
    content = response["output"]["message"]["content"]
    for block in content:
        if "toolUse" in block:
            tool_input: dict[str, Any] = block["toolUse"]["input"]
            return tool_input
    raise BedrockResponseError("Converse response contained no toolUse block")
