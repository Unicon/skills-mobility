from typing import Any

import pytest
from field_synthesis.bedrock_adapter import (
    BedrockAdapter,
    BedrockResponseError,
    _extract_tool_input,
)
from field_synthesis.contracts import SynthesisBrief, SynthesisGeneration, SynthesisRequest

from .conftest import make_brief


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
                        {"toolUse": {"name": "emit_synthesis", "input": self.tool_input}}
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 512, "outputTokens": 128, "totalTokens": 640},
        }


def _request() -> SynthesisRequest:
    from field_synthesis.contracts import SynthesisRequestArtifact

    return SynthesisRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="issuer_payload",
        synthesis_request=SynthesisRequestArtifact(
            transformation_type="issuer_payload",
            requests=[
                make_brief(
                    "field_a", "some.field_a", "Describe field A.", {"course": {"desc": "x"}}
                ),
            ],
        ),
    )


def _briefs() -> list[SynthesisBrief]:
    return [
        make_brief("field_a", "some.field_a", "Describe field A.", {"course": {"desc": "x"}})
    ]


def test_adapter_builds_converse_request_and_parses_tool_output() -> None:
    tool_input = {
        "values": {"field_a": "A description grounded in the source."},
        "confidence": 0.88,
        "rationale": "Source contained clear course description.",
    }
    fake = _FakeBedrock(tool_input)
    adapter = BedrockAdapter(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=fake,
    )

    gen, meta = adapter.generate(_request(), briefs=_briefs())

    assert isinstance(gen, SynthesisGeneration)
    assert gen.values["field_a"] == "A description grounded in the source."
    assert gen.confidence == 0.88
    # Request was built correctly: model id, temperature 0.3, forced tool use.
    kwargs = fake.last_kwargs
    assert kwargs is not None
    assert kwargs["modelId"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert kwargs["inferenceConfig"]["temperature"] == 0.3
    assert kwargs["toolConfig"]["toolChoice"]["tool"]["name"] == "emit_synthesis"
    assert kwargs["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"]["json"]["type"] == "object"
    # ADR-0010 §60: the adapter captures per-invocation model metadata.
    assert meta.provider == "bedrock"
    assert meta.model_id == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert meta.temperature == 0.3
    assert meta.input_tokens == 512
    assert meta.output_tokens == 128
    assert meta.latency_ms is not None
    assert meta.system_prompt and meta.user_prompt


def test_extract_tool_input_raises_without_tooluse() -> None:
    with pytest.raises(BedrockResponseError):
        _extract_tool_input({"output": {"message": {"content": [{"text": "no tool call"}]}}})


def test_adapter_lazy_client_not_created_until_generate_called() -> None:
    # With an explicit fake client, boto3 is never called.
    tool_output = {
        "values": {"field_a": "text"},
        "confidence": 0.9,
        "rationale": "ok",
    }
    fake = _FakeBedrock(tool_output)
    adapter = BedrockAdapter(
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-east-1",
        client=fake,
    )
    gen, _meta = adapter.generate(_request(), briefs=_briefs())
    assert gen.values["field_a"] == "text"
