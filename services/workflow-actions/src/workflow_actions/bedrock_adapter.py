"""Bedrock provider adapter (design §7 / ADR-0010).

A thin adapter over Bedrock's Converse API. It screens the event and context for
prompt injection (ADR-0021), builds each stage's prompt, and forces a
schema-constrained structured response via tool use, at temperature 0.

The configured model_id should be an inference-profile id (e.g.
``us.anthropic.claude-haiku-4-5-20251001-v1:0``). Credentials come from the
normal AWS SDK credential chain; no API-key layer.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import boto3

from .contracts import (
    GateGeneration,
    GateRequest,
    LlmCallMeta,
    PlanGeneration,
    PlanRequest,
)
from .prompt_builder import (
    build_gate_user_message,
    build_plan_user_message,
    gate_system_prompt,
    plan_system_prompt,
)
from .screen import screen_context

logger = logging.getLogger(__name__)

_GATE_TOOL_NAME = "emit_gate_decision"
_PLAN_TOOL_NAME = "emit_plan"
_TEMPERATURE = 0.0


class BedrockResponseError(Exception):
    """The Converse response did not contain the expected structured tool output."""


class BedrockAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        max_tokens: int = 2048,
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

    def _converse(
        self, *, system_text: str, user_text: str, tool_name: str, tool_desc: str,
        tool_schema: dict[str, Any],
    ) -> tuple[dict[str, Any], LlmCallMeta]:
        """Run one forced-tool-use Converse call and capture its §60 metadata."""
        started = time.perf_counter()
        response = self._bedrock().converse(
            modelId=self._model_id,
            system=[{"text": system_text}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": _TEMPERATURE, "maxTokens": self._max_tokens},
            toolConfig={
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool_name,
                            "description": tool_desc,
                            "inputSchema": {"json": tool_schema},
                        }
                    }
                ],
                "toolChoice": {"tool": {"name": tool_name}},
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
            system_prompt=system_text,
            user_prompt=user_text,
        )
        return response, meta

    def gate(
        self, request: GateRequest, *, gating_prose: str
    ) -> tuple[GateGeneration, LlmCallMeta]:
        # Screen free-text before it reaches the prompt.
        findings = screen_context(request.context_bundle)
        findings += screen_context({"event": request.event})
        if findings:
            logger.warning(
                "prompt-injection screen flagged values: %s",
                [f.path for f in findings],
            )

        response, meta = self._converse(
            system_text=gate_system_prompt(gating_prose),
            user_text=build_gate_user_message(request),
            tool_name=_GATE_TOOL_NAME,
            tool_desc="Emit the gate decision.",
            tool_schema=GateGeneration.model_json_schema(),
        )
        return GateGeneration(**_extract_tool_input(response)), meta

    def plan(
        self, request: PlanRequest, *, registry_view: list[dict[str, str]]
    ) -> tuple[PlanGeneration, LlmCallMeta]:
        # Screen free-text before it reaches the prompt.
        findings = screen_context(request.context_bundle)
        findings += screen_context({"event": request.event})
        if findings:
            logger.warning(
                "prompt-injection screen flagged values: %s",
                [f.path for f in findings],
            )

        response, meta = self._converse(
            system_text=plan_system_prompt(registry_view),
            user_text=build_plan_user_message(request),
            tool_name=_PLAN_TOOL_NAME,
            tool_desc="Emit the delivery-phase plan.",
            tool_schema=PlanGeneration.model_json_schema(),
        )
        return PlanGeneration(**_extract_tool_input(response)), meta


def _extract_tool_input(response: dict[str, Any]) -> dict[str, Any]:
    content = response["output"]["message"]["content"]
    for block in content:
        if "toolUse" in block:
            tool_input: dict[str, Any] = block["toolUse"]["input"]
            return tool_input
    raise BedrockResponseError("Converse response contained no toolUse block")
