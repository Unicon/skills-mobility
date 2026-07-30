"""POST /api/v1/token — OAuth2 client_credentials token endpoint (design §3).

Validates the Basic-auth pair against the configured ClientID/AccessKey (FR-MSR-2,
mirroring FR-MSR-6's Bearer comparison); a match returns the fixed canned token so
tests can assert on it. Auth uses ``fastapi.security.HTTPBasic`` (not a raw
``Header()``) so Swagger UI renders a working "Authorize" control — the
``anyOf: [string, null]`` schema a nullable Header parameter produces is known to
drop the header silently in Swagger's "Try it out".
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from mock_smartresume.config import Settings
from mock_smartresume.schemas import TokenResponse
from mock_smartresume.token_store import CANNED_TOKEN

router = APIRouter(prefix="/api/v1", tags=["token"])

# auto_error=False so a missing/malformed header raises OUR 401 (not a 403).
_basic = HTTPBasic(auto_error=False)


def _require_basic(credentials: HTTPBasicCredentials | None, settings: Settings) -> None:
    """Require a Basic pair matching the configured ClientID/AccessKey (FR-MSR-1/2)."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing Basic authorization")
    if credentials.username != settings.client_id or credentials.password != settings.access_key:
        raise HTTPException(status_code=401, detail="invalid ClientID or AccessKey")


@router.post("/token")
def issue_token(
    request: Request,
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)] = None,
    grant_type: Annotated[str | None, Form()] = None,
    scope: Annotated[str | None, Form()] = None,
) -> TokenResponse:
    settings: Settings = request.app.state.settings
    _require_basic(credentials, settings)
    # grant_type is validated here (not as a required Form field) so an absent or
    # wrong value returns 400, not FastAPI's default 422 (FR-MSR-3).
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail="unsupported grant_type")
    return TokenResponse(access_token=CANNED_TOKEN)
