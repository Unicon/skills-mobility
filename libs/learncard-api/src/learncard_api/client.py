"""Authenticated client for the LearnCloud Network REST API.

Thin wrapper over ``httpx.Client``: it attaches the scoped bearer, points at the
configured base URL, and raises on error responses (no silent drops). Endpoint
shapes (request/response models for ``/send``, ``/profile``, ...) are owned by the
calling service — the Profile Resolver (#41) and Wallet Adapter (#43) — since the
shared concern here is auth + transport, not the specific payloads.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from learncard_api.config import LearnCardSettings


class LearnCardClient:
    """Bearer-authenticated REST client for the LearnCloud Network API.

    A ``transport`` may be injected for tests (e.g. ``httpx.MockTransport``) so
    the auth header and base URL this client builds are exercised without a
    network call.
    """

    def __init__(
        self,
        settings: LearnCardSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=settings.api_url,
            headers={"Authorization": f"Bearer {settings.api_token}"},
            timeout=30.0,
            transport=transport,
        )

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.get(path, **kwargs)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body

    def post(self, path: str, json: Any | None = None, **kwargs: Any) -> dict[str, Any]:
        resp = self._client.post(path, json=json, **kwargs)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json()
        return body

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LearnCardClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
