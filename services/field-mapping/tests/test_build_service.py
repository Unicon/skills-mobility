"""Tests for build_service wiring (item 6 of PR review).

These tests verify that Settings → MappingService adapter wiring is correct
without requiring any AWS credentials (the boto3 client is lazy).
"""

from __future__ import annotations

import pytest
from field_mapping.api import build_service
from field_mapping.bedrock_adapter import BedrockAdapter
from field_mapping.config import Settings
from field_mapping.replay_adapter import ReplayAdapter


def test_build_service_replay_mode_yields_replay_adapter() -> None:
    svc = build_service(Settings(mode="replay"))
    assert isinstance(svc._adapter, ReplayAdapter)


def test_build_service_bedrock_mode_yields_bedrock_adapter_with_correct_settings() -> None:
    settings = Settings(
        mode="bedrock",
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        aws_region="us-west-2",
        max_tokens=2048,
    )
    svc = build_service(settings)
    assert isinstance(svc._adapter, BedrockAdapter)
    # Internal attributes match the settings (boto3 client is lazy — no AWS call).
    assert svc._adapter._model_id == settings.model_id
    assert svc._adapter._region == settings.aws_region
    assert svc._adapter._max_tokens == settings.max_tokens


def test_build_service_unknown_mode_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown adapter mode"):
        build_service(Settings(mode="not_a_real_mode"))
