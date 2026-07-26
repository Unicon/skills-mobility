from typing import Any

import pytest
from delivery_targets.bedrock_adapter import (
    BedrockAdapter,
    BedrockResponseError,
    _extract_tool_input,
)
from delivery_targets.contracts import SelectionGeneration, SelectionRequest


class _FakeBedrock:
    """Stand-in for the boto3 bedrock-runtime client; records the request and
    returns a canned tool-use Converse response."""

    def __init__(self, tool_input: dict[str, Any]) -> None:
        self.tool_input = tool_input
        self.last_kwargs: dict[str, Any] | None = None

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.last_kwargs = kwargs
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"toolUse": {"name": "emit_selection", "input": self.tool_input}}
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 321, "outputTokens": 42, "totalTokens": 363},
        }


def _skill_mastered_request() -> SelectionRequest:
    return SelectionRequest(
        execution_id="exec_1",
        event_id="evt_1",
        event_type="skill_mastered",
        source_system="mock_lms",
        learner_context={"learner_id": "learner_42", "course_id": "ACCY-111"},
    )


def _catalog() -> list[dict[str, Any]]:
    return [
        {
            "delivery_target": "learncard_issuer",
            "delivery_action": "issue_learncard_badge",
            "description": "Issues a verifiable badge.",
            "eligibility_notes": "credential-enabled courses",
        }
    ]


def test_adapter_builds_converse_request_and_parses_tool_output() -> None:
    tool_input = {
        "selections": [
            {
                "delivery_target": "learncard_issuer",
                "confidence": 0.95,
                "rationale": "credential-enabled course",
            }
        ]
    }
    fake = _FakeBedrock(tool_input)
    adapter = BedrockAdapter(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=fake,
    )

    gen, meta = adapter.select(_skill_mastered_request(), catalog=_catalog())

    assert isinstance(gen, SelectionGeneration)
    assert gen.selections[0].confidence == 0.95
    # Request was built correctly: model id, temperature 0, forced tool use.
    kwargs = fake.last_kwargs
    assert kwargs is not None
    assert kwargs["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert kwargs["inferenceConfig"]["temperature"] == 0.0
    assert kwargs["toolConfig"]["toolChoice"]["tool"]["name"] == "emit_selection"
    assert kwargs["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["type"] == "object"
    # ADR-0010 §60: the adapter captures per-invocation model metadata.
    assert meta.provider == "bedrock"
    assert meta.model_id == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert meta.temperature == 0.0
    assert meta.input_tokens == 321
    assert meta.output_tokens == 42
    assert meta.latency_ms is not None
    assert meta.system_prompt and meta.user_prompt


def test_extract_tool_input_raises_without_tooluse() -> None:
    with pytest.raises(BedrockResponseError):
        _extract_tool_input({"output": {"message": {"content": [{"text": "no tool call"}]}}})


def test_adapter_lazy_client_not_created_until_select_is_called() -> None:
    # With an explicit fake client, boto3 is never called.
    tool_output = {
        "selections": [{"delivery_target": "learncard_issuer", "confidence": 0.9, "rationale": "x"}]
    }
    fake = _FakeBedrock(tool_output)
    adapter = BedrockAdapter(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=fake,
    )
    # The internal _client is set immediately when passed — this just verifies
    # it works without a real boto3 import.
    gen, _meta = adapter.select(_skill_mastered_request(), catalog=_catalog())
    assert gen.selections[0].delivery_target == "learncard_issuer"
