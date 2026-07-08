"""Delivered-credential read-back (#53, ADR-0020).

Proves a delivered credential actually landed in the demo recipient wallet, for
the Admin UI. Fully **read-only** (recipient `credentials:read` token, verified
live): find the delivery `uri` in the wallet's credential lists, then resolve the
full VC to render. No accept/write.

A delivered credential sits in `incoming` (pending) until accepted, after which
it moves to the separate `received` list — so we check both, and page through
each, because the fixed demo wallet (ADR-0020) is reused across runs and its
lists only grow.

ASSUMPTION (verified once live, #53 — not a documented contract): the bare string
`POST /credential/send` returns as `external_reference_id` is format-compatible
with the `uri` field in these lists and with `/storage/resolve?uri=`. If a future
live check shows `/storage/resolve` is recipient-gated, the list scan below could
be dropped in favor of resolving the URI directly (see the PR #55 discussion).
"""

from __future__ import annotations

from typing import Any

from learncard_api import LearnCardClient

from learncard_wallet_adapter.schemas import DeliveredCredential

# Documented max page size for /credentials/incoming and /credentials/received.
_PAGE_SIZE = 100


def _find_in_list(client: LearnCardClient, path: str, uri: str) -> dict[str, Any] | None:
    """Page through a wallet credential list (`incoming`/`received`) for `uri`.

    Pages with `limit` + a `from` cursor (the previous page's last `uri`) until
    the entry is found or a short/empty page marks the end — reading only the
    first page would miss credentials once the demo wallet grows past one page.
    The `from`-cursor semantics are part of the live-verified assumption noted in
    the module docstring."""
    cursor: str | None = None
    while True:
        params: dict[str, Any] = {"limit": _PAGE_SIZE}
        if cursor is not None:
            params["from"] = cursor
        page: list[dict[str, Any]] = client.request("GET", path, params=params).json()
        match = next((c for c in page if c.get("uri") == uri), None)
        if match is not None:
            return match
        if len(page) < _PAGE_SIZE:
            return None  # last page reached; not found
        next_cursor = page[-1].get("uri")
        if next_cursor is None or next_cursor == cursor:
            return None  # can't advance safely — stop rather than loop forever
        cursor = next_cursor


def read_delivered(recipient_client: LearnCardClient, uri: str) -> DeliveredCredential:
    """Look for `uri` in the recipient wallet (incoming, then the accepted
    `received` list); if present, resolve and return the VC. `uri` is the
    `external_reference_id` returned by delivery."""
    match = _find_in_list(recipient_client, "/credentials/incoming", uri)
    if match is None:
        # Accepted credentials move out of `incoming` into `received`; check there
        # so an accepted credential still reads back as delivered (#53).
        match = _find_in_list(recipient_client, "/credentials/received", uri)
    if match is None:
        return DeliveredCredential(delivered=False)
    credential: dict[str, Any] = recipient_client.request(
        "GET", "/storage/resolve", params={"uri": uri}
    ).json()
    return DeliveredCredential(
        delivered=True,
        recipient_profile_id=match.get("to"),
        sent_at=match.get("sent"),
        credential=credential,
    )
