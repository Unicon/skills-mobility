"""Orchestrator handoff seam: capture-mode vs HTTP-mode."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
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
    # HTTP-mode handoff advances the execution status to handoff_sent.
    assert store.get_execution(result.execution_id)["status"] == "handoff_sent"


def test_http_handoff_raises_on_non_2xx(store, skill_event):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://orchestrator")
    http = HttpHandoff("http://orchestrator", client=client)

    # A non-2xx from the Orchestrator must surface, not be silently swallowed.
    with pytest.raises(httpx.HTTPStatusError):
        consumer.process(skill_event(), store, http)


def test_duplicate_does_not_hand_off(store, skill_event):
    calls: list[str] = []

    class SpyHandoff:
        def hand_off(self, execution_id: str, event: dict[str, Any]) -> str:
            calls.append(execution_id)
            return "handoff_sent"

    spy = SpyHandoff()
    consumer.process(skill_event(event_id="evt_1"), store, spy)
    consumer.process(skill_event(event_id="evt_1_redelivered"), store, spy)

    assert len(calls) == 1  # only the first (created); the duplicate is short-circuited


def test_http_handoff_reset_downstream_posts_admin_reset():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True})

    handoff = HttpHandoff(
        "http://orch", client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://orch")
    )
    assert handoff.reset_downstream() == "reset"
    assert seen["url"] == "http://orch/admin/reset"


def test_http_handoff_reset_downstream_reports_unreachable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    handoff = HttpHandoff(
        "http://orch", client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://orch")
    )
    assert handoff.reset_downstream() == "unreachable"
