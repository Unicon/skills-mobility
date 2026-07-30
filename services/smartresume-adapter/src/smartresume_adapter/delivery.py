"""SmartResume delivery call — token acquisition + ``/credentials`` POST.

Owns the OAuth2 ``client_credentials`` token exchange and the JSON body
assembly from the incoming router payload (design §4, step 5). Auth + transport
use ``httpx``; no vendor SDK. This is the only place SmartResume-specific body
construction lives, and it stays mechanical: field copy, ``@context`` set,
``proof`` pass-through, ``targetName`` truncation.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from smartresume_adapter.schemas import DeliverPayload

logger = logging.getLogger("smartresume_adapter")

# VC v1 + OBv3 context (design §4, step 5).
CONTEXT = [
    "https://www.w3.org/2018/credentials/v1",
    "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
]

# SmartResume caps alignment[].targetName at 40 chars (requirements FR-SR-8).
_TARGET_NAME_MAX = 40


class TokenError(httpx.HTTPError):
    """Raised when the token exchange returns a non-2xx response."""


def _truncate_alignment(credential: dict[str, Any]) -> None:
    """Enforce the 40-char targetName limit in-place, logging a warning (FR-SR-8)."""
    alignment = (
        credential.get("credentialSubject", {}).get("achievement", {}).get("alignment")
    )
    if not isinstance(alignment, list):
        return
    for entry in alignment:
        name = entry.get("targetName")
        if isinstance(name, str) and len(name) > _TARGET_NAME_MAX:
            logger.warning(
                "truncating alignment targetName from %d to %d chars",
                len(name),
                _TARGET_NAME_MAX,
            )
            entry["targetName"] = name[:_TARGET_NAME_MAX]


def build_body(payload: DeliverPayload) -> dict[str, Any]:
    """Assemble the SmartResume ``/credentials`` body from the incoming payload.

    Mechanical mapping only: sets ``@context``, forwards ``recipient`` and the
    already-shaped ``credentials`` verbatim (``proof`` included only when the
    incoming credential carries one), and forwards ``recipienttoken`` if present.
    """
    credentials: list[dict[str, Any]] = []
    for credential in payload.credentials:
        # Copy so truncation never mutates the caller's request model.
        entry = dict(credential)
        _truncate_alignment(entry)
        credentials.append(entry)

    body: dict[str, Any] = {
        "@context": CONTEXT,
        "recipient": payload.recipient.model_dump(exclude_none=True),
        "credentials": credentials,
    }
    if payload.recipienttoken is not None:
        body["recipienttoken"] = payload.recipienttoken
    return body


def acquire_token(client: httpx.Client, base_url: str, client_id: str, access_key: str) -> str:
    """Obtain an OAuth2 access token via ``POST /api/v1/token`` (FR-SR-4)."""
    resp = client.post(
        f"{base_url.rstrip('/')}/api/v1/token",
        auth=(client_id, access_key),
        data={"grant_type": "client_credentials", "scope": "delete readonly replace"},
    )
    if resp.status_code // 100 != 2:
        raise TokenError(f"token exchange failed with HTTP {resp.status_code}")
    token: str = resp.json()["access_token"]
    return token


def deliver(
    client: httpx.Client,
    base_url: str,
    client_id: str,
    access_key: str,
    payload: DeliverPayload,
) -> httpx.Response:
    """Acquire a fresh token, then POST the assembled body to ``/credentials``.

    Returns the raw ``/credentials`` response; result normalization is the
    caller's (resultmap) concern.
    """
    token = acquire_token(client, base_url, client_id, access_key)
    return client.post(
        f"{base_url.rstrip('/')}/api/v1/credentials",
        headers={"Authorization": f"Bearer {token}"},
        json=build_body(payload),
    )
