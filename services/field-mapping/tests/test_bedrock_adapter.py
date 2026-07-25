from typing import Any

import pytest
from field_mapping.bedrock_adapter import BedrockAdapter, BedrockResponseError, _extract_tool_input
from field_mapping.contracts import MappingGeneration, MappingRequest


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
                    "content": [{"toolUse": {"name": "emit_mapping", "input": self.tool_input}}],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 512, "outputTokens": 88, "totalTokens": 600},
        }


def _wallet_request() -> MappingRequest:
    return MappingRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="wallet_payload",
        source_system="mock_lms",
        fetch_profile_id="skill_mastered.v1",
        delivery_target="learncard_wallet",
        synthesis_allowed=False,
        source_payloads={
            "profile_resolution": {"recipient_profile_id": "smi-demo-learner"},
            "issued_badge": {"proof": {"type": "DataIntegrityProof"}},
        },
    )


def test_adapter_builds_converse_request_and_parses_tool_output() -> None:
    tool_input = {
        "jsonata": (
            '{ "recipient_profile_id": source_payloads.profile_resolution.recipient_profile_id, '
            '"signed_credential": source_payloads.issued_badge }'
        ),
        "placeholder_ids": [],
        "synthesis_requests": [],
        "confidence": 0.95,
        "rationale": "direct pass-through",
    }
    fake = _FakeBedrock(tool_input)
    adapter = BedrockAdapter(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=fake,
    )

    gen, meta = adapter.generate(
        _wallet_request(), target_schema={"required": ["recipient_profile_id"]}
    )

    assert isinstance(gen, MappingGeneration)
    assert gen.confidence == 0.95
    # request was built per design §9: right model id, temperature 0, forced tool use
    kwargs = fake.last_kwargs
    assert kwargs is not None
    assert kwargs["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert kwargs["inferenceConfig"]["temperature"] == 0.0
    assert kwargs["toolConfig"]["toolChoice"]["tool"]["name"] == "emit_mapping"
    assert kwargs["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["type"] == "object"
    # ADR-0010 §60: the adapter captures per-invocation model metadata.
    assert meta.provider == "bedrock"
    assert meta.input_tokens == 512
    assert meta.output_tokens == 88
    assert meta.latency_ms is not None
    assert meta.system_prompt and meta.user_prompt


def test_extract_tool_input_raises_without_tooluse() -> None:
    with pytest.raises(BedrockResponseError):
        _extract_tool_input({"output": {"message": {"content": [{"text": "no tool call"}]}}})
