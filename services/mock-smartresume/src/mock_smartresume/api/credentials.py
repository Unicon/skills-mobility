"""POST /api/v1/credentials — credential delivery endpoint (design §3).

Requires the canned Bearer token, minimally validates the OB3-shaped body
(recipient.id + at least one credential with an achievement id), and returns a
deterministic ``redirect_url``. ``proof`` is optional (verified vs unverified
paths both accepted). Stateless — the response is computed from the body alone.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException

from mock_smartresume.schemas import CredentialsResponse
from mock_smartresume.token_store import CANNED_TOKEN, derive_redirect_token

router = APIRouter(prefix="/api/v1", tags=["credentials"])

REDIRECT_BASE = "https://mock.smartresume.example/createmyresume/"


def _require_bearer(authorization: str | None) -> None:
    if authorization != f"Bearer {CANNED_TOKEN}":
        raise HTTPException(status_code=401, detail="missing or invalid Bearer token")


def _first_credential_id(body: dict[str, Any]) -> str:
    """Validate the OB3 body minimally; return the first credential id (FR-MSR-7)."""
    recipient = body.get("recipient")
    if not isinstance(recipient, dict) or not recipient.get("id"):
        raise HTTPException(status_code=400, detail="recipient.id is required")

    credentials = body.get("credentials")
    if not isinstance(credentials, list) or not credentials:
        raise HTTPException(status_code=400, detail="at least one credential is required")

    for credential in credentials:
        if not isinstance(credential, dict) or not credential.get("id"):
            raise HTTPException(status_code=400, detail="credential.id is required")
        achievement = credential.get("credentialSubject", {}).get("achievement", {})
        if not isinstance(achievement, dict) or not achievement.get("id"):
            raise HTTPException(
                status_code=400, detail="credentialSubject.achievement.id is required"
            )

    first_id: str = credentials[0]["id"]
    return first_id


@router.post("/credentials")
def deliver(
    body: Annotated[dict[str, Any], Body()],
    authorization: Annotated[str | None, Header()] = None,
) -> CredentialsResponse:
    _require_bearer(authorization)
    credential_id = _first_credential_id(body)
    token = derive_redirect_token(body["recipient"]["id"], credential_id)
    return CredentialsResponse(redirect_url=f"{REDIRECT_BASE}{token}")
