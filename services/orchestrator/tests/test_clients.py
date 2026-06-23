"""The real HTTP Context Builder client — POST shape + response passthrough."""

from __future__ import annotations

import json

import httpx
from orchestrator.clients import HttpContextBuilderClient


def test_http_context_builder_posts_and_returns_bundle():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "execution_id": "e1",
                "event_type": "skill_mastered",
                "source_data": {"outcome": {}},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://cb")
    cb = HttpContextBuilderClient("http://cb", client=client)
    bundle = cb.build_context("e1", {"metadata": {"event_name": "learning_outcome_result_created"}})

    assert captured["path"] == "/internal/build-context"
    assert captured["body"] == {
        "execution_id": "e1",
        "event": {"metadata": {"event_name": "learning_outcome_result_created"}},
    }
    assert bundle["event_type"] == "skill_mastered"
