"""POST /api/v1/token — OAuth2 client_credentials token endpoint (design §3).

Permissive by design: any non-empty ClientID/AccessKey pair is accepted. The
returned token is the fixed canned constant so tests can assert on it.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Form, Header, HTTPException

from mock_smartresume.schemas import TokenResponse
from mock_smartresume.token_store import CANNED_TOKEN

router = APIRouter(prefix="/api/v1", tags=["token"])


def _require_basic(authorization: str | None) -> None:
    """Accept any non-empty ClientID:AccessKey Basic pair; else 401 (FR-MSR-1/2)."""
    if authorization is None or not authorization.lower().startswith("basic "):
        raise HTTPException(status_code=401, detail="missing Basic authorization")
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1]).decode()
    except (binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="malformed Basic authorization") from None
    client_id, _, access_key = decoded.partition(":")
    if not client_id or not access_key:
        raise HTTPException(status_code=401, detail="empty ClientID or AccessKey")


@router.post("/token")
def issue_token(
    authorization: Annotated[str | None, Header()] = None,
    grant_type: Annotated[str | None, Form()] = None,
    scope: Annotated[str | None, Form()] = None,
) -> TokenResponse:
    _require_basic(authorization)
    # grant_type is validated here (not as a required Form field) so an absent or
    # wrong value returns 400, not FastAPI's default 422 (FR-MSR-3).
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported grant_type")
    return TokenResponse(access_token=CANNED_TOKEN)
