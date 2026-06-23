"""Orchestrator handoff seam: capture-mode vs HTTP-mode."""

from __future__ import annotations

import json
from typing import Any

import httpx
from event_consumer import consumer
from event_consumer.handoff import HttpHandoff


def test_created_event_posts_to_orchestrator(store, skill_event):
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "ok"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="http://orchestrator")
    http = HttpHandoff("http://orchestrator", client=client)

    result = consumer.process(skill_event(), store, http)

    assert result.status == "created"
    assert seen["url"] == "http://orchestrator/run-workflow"
    assert seen["body"]["execution_id"] == result.execution_id
    assert seen["body"]["event"]["metadata"]["event_id"] == "evt_1"


def test_duplicate_does_not_hand_off(store, skill_event):
    calls: list[str] = []

    class SpyHandoff:
        def hand_off(self, execution_id: str, event: dict[str, Any]) -> None:
            calls.append(execution_id)

    spy = SpyHandoff()
    consumer.process(skill_event(event_id="evt_1"), store, spy)
    consumer.process(skill_event(event_id="evt_1_redelivered"), store, spy)

    assert len(calls) == 1  # only the first (created); the duplicate is short-circuited
