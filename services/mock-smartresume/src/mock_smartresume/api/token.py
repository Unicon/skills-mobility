"""POST /api/v1/token — OAuth2 client_credentials token endpoint (design §3).

Validates the Basic-auth pair against the configured ClientID/AccessKey (FR-MSR-2,
mirroring FR-MSR-6's Bearer comparison); a match returns the fixed canned token so
tests can assert on it.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Form, Header, HTTPException, Request

from mock_smartresume.config import Settings
from mock_smartresume.schemas import TokenResponse
from mock_smartresume.token_store import CANNED_TOKEN

router = APIRouter(prefix="/api/v1", tags=["token"])


def _require_basic(authorization: str | None, settings: Settings) -> None:
    """Require a Basic pair matching the configured ClientID/AccessKey (FR-MSR-1/2)."""
    if authorization is None or not authorization.lower().startswith("basic "):
        raise HTTPException(status_code=401, detail="missing Basic authorization")
    try:
        decoded = base64.b64decode(authorization.split(" ", 1)[1]).decode()
    except (binascii.Error, UnicodeDecodeError):
        raise HTTPException(status_code=401, detail="malformed Basic authorization") from None
    client_id, _, access_key = decoded.partition(":")
    if client_id != settings.client_id or access_key != settings.access_key:
        raise HTTPException(status_code=401, detail="invalid ClientID or AccessKey")


@router.post("/token")
def issue_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    grant_type: Annotated[str | None, Form()] = None,
    scope: Annotated[str | None, Form()] = None,
) -> TokenResponse:
    settings: Settings = request.app.state.settings
    _require_basic(authorization, settings)
    # grant_type is validated here (not as a required Form field) so an absent or
    # wrong value returns 400, not FastAPI's default 422 (FR-MSR-3).
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported grant_type")
    return TokenResponse(access_token=CANNED_TOKEN)
