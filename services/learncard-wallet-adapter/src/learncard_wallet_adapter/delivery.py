"""Service-specific LearnCard delivery call.

Sends an already-issued (signed) credential to the recipient's LearnCard wallet
via ``POST /credential/send/{profileId}`` (design §2). Auth + transport come
from the shared ``LearnCardClient`` (libs/learncard-api); this module owns only
the endpoint shape. That endpoint replies with a bare JSON string — the
credential URI — so it uses ``client.request`` and reads ``.json()`` directly.
"""

from __future__ import annotations

from typing import Any

from learncard_api import LearnCardClient


def deliver(
    client: LearnCardClient, recipient_profile_id: str, signed_credential: dict[str, Any]
) -> str:
    """Deliver the credential; return the credential URI LearnCard reports."""
    resp = client.request(
        "POST",
        f"/credential/send/{recipient_profile_id}",
        json={"credential": signed_credential},
    )
    uri: str = resp.json()
    return uri
