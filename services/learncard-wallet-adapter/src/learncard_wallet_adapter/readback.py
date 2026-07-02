"""Delivered-credential read-back (#53, ADR-0020).

Proves a delivered credential actually landed in the demo recipient wallet, for
the Admin UI. Fully **read-only** (recipient `credentials:read` token, verified
live): list the wallet's incoming credentials to confirm the delivery `uri` is
present, then resolve the full VC to render. No accept/write — a delivered
credential sits in `incoming` (pending) until accepted, which is enough proof
that it reached the wallet.
"""

from __future__ import annotations

from typing import Any

from learncard_api import LearnCardClient

from learncard_wallet_adapter.schemas import DeliveredCredential


def read_delivered(recipient_client: LearnCardClient, uri: str) -> DeliveredCredential:
    """Look for `uri` in the recipient wallet's incoming list; if present, resolve
    and return the VC. `uri` is the `external_reference_id` returned by delivery."""
    incoming: list[dict[str, Any]] = recipient_client.request("GET", "/credentials/incoming").json()
    match = next((c for c in incoming if c.get("uri") == uri), None)
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
