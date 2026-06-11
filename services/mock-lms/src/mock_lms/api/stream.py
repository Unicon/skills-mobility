"""Server-Sent Events live feed of emissions (design §4, recommended transport).

The UI opens ``GET /demo/stream`` and receives an ``emission`` event for each new
record as it lands, so a presenter's screen updates in real time. The handler
tails the in-memory emission log by cursor; backfill (history before the stream
opened) is available via ``GET /demo/emissions``. A periodic comment line keeps
the connection alive through proxies (e.g. CloudFront).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from mock_lms.api import get_emission_log
from mock_lms.emission import EmissionLog

router = APIRouter(prefix="/demo", tags=["emission"])

LogDep = Annotated[EmissionLog, Depends(get_emission_log)]

_POLL_SECONDS = 0.4
_HEARTBEAT_EVERY = 15.0


async def _emission_events(request: Request, log: EmissionLog, since: int) -> AsyncIterator[str]:
    cursor = since
    # Tell the client where to resume from if it reconnects.
    yield f"retry: 3000\nevent: cursor\ndata: {json.dumps({'cursor': cursor})}\n\n"
    idle = 0.0
    while True:
        if await request.is_disconnected():
            break
        new = log.since(cursor)
        for record in new:
            cursor = record.seq
            yield f"event: emission\ndata: {json.dumps(record.to_public_dict())}\n\n"
        if new:
            idle = 0.0
        else:
            idle += _POLL_SECONDS
            if idle >= _HEARTBEAT_EVERY:
                idle = 0.0
                yield ": keepalive\n\n"
        await asyncio.sleep(_POLL_SECONDS)


@router.get("/stream")
async def stream_emissions(request: Request, log: LogDep, since: int = 0) -> StreamingResponse:
    return StreamingResponse(
        _emission_events(request, log, since),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
