"""HTTP client boundary for the Mock LMS Resource APIs.

The engine depends only on the ``LMSClient`` protocol, so tests can inject a
fake without touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx


@dataclass(frozen=True)
class LMSResponse:
    status_code: int
    data: Any  # parsed JSON body (or None if the body wasn't JSON)


class LMSClient(Protocol):
    def get(self, path: str) -> LMSResponse: ...


class HttpxLMSClient:
    """Real client: GETs ``{base_url}{path}`` against the Mock LMS."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def get(self, path: str) -> LMSResponse:
        # Percent-encode reserved characters (Canvas-style include[]=/uuids[]=
        # brackets) while leaving path separators and query structure intact.
        # httpx passes brackets through verbatim (fine against local uvicorn)
        # but Lambda Function URLs mishandle them (first live AWS run). "%" is
        # safe so already-encoded input stays untouched (idempotent).
        resp = self._client.get(quote(path, safe="/=&?%"))
        try:
            data: Any = resp.json()
        except ValueError:
            data = None
        return LMSResponse(status_code=resp.status_code, data=data)

    def close(self) -> None:
        self._client.close()
