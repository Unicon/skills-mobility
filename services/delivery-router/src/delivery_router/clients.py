"""Thin HTTP client for downstream adapters.

Mechanical request assembly + a deterministic, config-driven retry on transport
errors (connection/timeout). It does NOT retry on an adapter's ``failed`` status
— that is a business result, not a transport fault. Adapter-specific field
mapping does not belong here.
"""

from __future__ import annotations

from typing import Any

import httpx


class AdapterClient:
    def __init__(
        self,
        *,
        timeout: float = 30.0,
        retry_limit: int = 1,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(timeout=timeout, transport=transport)
        self._retry_limit = retry_limit

    def post(self, url: str, json: dict[str, Any]) -> dict[str, Any]:
        attempt = 0
        while True:
            try:
                resp = self._client.post(url, json=json)
                resp.raise_for_status()
                body: dict[str, Any] = resp.json()
                return body
            except httpx.TransportError:
                if attempt >= self._retry_limit:
                    raise
                attempt += 1

    def close(self) -> None:
        self._client.close()
