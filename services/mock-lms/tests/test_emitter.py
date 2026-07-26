"""LocalEmitter: in-process capture, plus optional forward to the Event Consumer."""

import json

import httpx
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
