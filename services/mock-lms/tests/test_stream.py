"""SSE live-feed behavior (design §4).

Drives the event generator directly with a fake request rather than the
streaming TestClient, which deadlocks on a sync client + async generator.
"""

import asyncio
import json

from mock_lms.api.stream import _emission_events
from mock_lms.emission import EmissionLog, EmissionRecord
from skills_mobility_events import LiveEventEnvelope, new_event_id


class _FakeRequest:
    """Reports connected for the first N disconnect checks, then disconnected."""

    def __init__(self, alive_checks: int = 1) -> None:
        self._left = alive_checks

    async def is_disconnected(self) -> bool:
        if self._left <= 0:
            return True
        self._left -= 1
        return False


def _record(seq_name: str) -> EmissionRecord:
    env = LiveEventEnvelope.model_validate(
        {
            "metadata": {
                "event_name": "learning_outcome_result_created",
                "event_time": "2026-06-10T17:00:00Z",
                "event_id": new_event_id(),
                "correlation_id": "corr_test",
            },
            "body": {"mastery": True},
        }
    )
    return EmissionRecord(
        emission_id="emis_test",
        correlation_id="corr_test",
        event_type="skill_mastered",
        event_name=env.metadata.event_name,
        event_time=env.metadata.event_time,
        target="local-bus",
        envelope=env.model_dump(mode="json"),
    )


def _collect(gen) -> list[str]:
    async def run() -> list[str]:
        return [chunk async for chunk in gen]

    return asyncio.run(run())


def test_stream_emits_cursor_then_buffered_emissions():
    log = EmissionLog()
    log.append(_record("a"))
    chunks = _collect(_emission_events(_FakeRequest(alive_checks=1), log, since=0))
    blob = "".join(chunks)

    assert "event: cursor" in blob
    assert "event: emission" in blob
    # The emission payload is valid JSON with the Canvas event name.
    data_line = next(
        line for line in blob.splitlines() if line.startswith("data:") and "event_name" in line
    )
    payload = json.loads(data_line.split(":", 1)[1].strip())
    assert payload["event_name"] == "learning_outcome_result_created"


def test_stream_resumes_from_cursor_and_skips_old():
    log = EmissionLog()
    log.append(_record("a"))  # seq 1
    log.append(_record("b"))  # seq 2
    chunks = _collect(_emission_events(_FakeRequest(alive_checks=1), log, since=1))
    emission_chunks = [c for c in chunks if "event: emission" in c]
    # Only seq 2 should be streamed (seq 1 is <= cursor).
    assert len(emission_chunks) == 1
