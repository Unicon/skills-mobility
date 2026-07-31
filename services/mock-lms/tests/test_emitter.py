"""LocalEmitter: in-process capture, plus optional forward to the Event Consumer."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from mock_lms.app import create_app
from mock_lms.config import Settings
from mock_lms.emitter import LocalEmitter
from skills_mobility_events import LiveEventEnvelope


def _an_envelope() -> LiveEventEnvelope:
    """Emit a real skill-mastery event through the app and grab the envelope."""
    # event_consumer_url=None so a developer's local .env can't turn the emitter
    # into a forwarding one that fires at a real (or dead) event-consumer.
    app = create_app(Settings(emitter="local", event_consumer_url=None))
    client = TestClient(app)
    courses = client.get("/demo/courses").json()
    std = next(c for c in courses if c["kind"] == "standard")
    client.post(
        f"/demo/courses/{std['id']}/actions",
        json={"action_id": f"{std['id']}-grade-m1", "scope": "one"},
    )
    emitted = app.state.emitter.emitted
    assert emitted, "the action should have emitted an envelope"
    return emitted[0]


def test_forwards_envelope_to_event_consumer_ingest():
    envelope = _an_envelope()
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "created"})

    transport = httpx.MockTransport(handler)
    emitter = LocalEmitter(client=httpx.Client(transport=transport, base_url="http://ec"))
    emitter.emit(envelope)

    assert emitter.emitted == [envelope]  # still captured in-process
    assert seen["url"] == "http://ec/ingest"
    assert seen["body"] == envelope.model_dump(mode="json")


def test_without_forward_url_only_captures():
    envelope = _an_envelope()
    emitter = LocalEmitter()  # no forward_url → no HTTP client, capture only
    emitter.emit(envelope)
    assert emitter.emitted == [envelope]


def test_reset_downstream_propagates_both_hops():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"ok": True, "cleared": 2, "orchestrator": "reset"})

    emitter = LocalEmitter(
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ec")
    )
    assert emitter.reset_downstream() == {"event_consumer": "reset", "orchestrator": "reset"}
    assert seen["url"] == "http://ec/reset"


def test_reset_downstream_surfaces_a_failed_terminus():
    # The EC hop succeeding must not mask a failed orchestrator hop (found live:
    # the terminus 500'd while the top-level response claimed success).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True, "orchestrator": "unreachable"})

    emitter = LocalEmitter(
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ec")
    )
    assert emitter.reset_downstream() == {
        "event_consumer": "reset",
        "orchestrator": "unreachable",
    }


def test_reset_downstream_without_forwarding_is_not_configured():
    assert LocalEmitter().reset_downstream() == {
        "event_consumer": "not_configured",
        "orchestrator": "not_configured",
    }


def test_reset_downstream_reports_unreachable_on_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    emitter = LocalEmitter(
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ec")
    )
    assert emitter.reset_downstream() == {
        "event_consumer": "unreachable",
        "orchestrator": "unknown",
    }


def test_emit_tolerates_slow_chain_but_raises_on_undelivered():
    # A ReadTimeout means the request WAS delivered and the synchronous chain is
    # still running — the fire must not hang or fail on it. A connect error
    # means the event never arrived — that must stay loud.
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("chain still running", request=request)

    emitter = LocalEmitter(
        client=httpx.Client(transport=httpx.MockTransport(slow), base_url="http://ec")
    )
    emitter.emit(_an_envelope())  # does not raise
    assert len(emitter.emitted) == 1

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("nobody home", request=request)

    broken = LocalEmitter(
        client=httpx.Client(transport=httpx.MockTransport(down), base_url="http://ec")
    )
    with pytest.raises(httpx.ConnectError):
        broken.emit(_an_envelope())
