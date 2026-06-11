"""Auth boundary for the Mock LMS service.

Per ADR-0002 the POC authenticates at the CloudFront layer; the service simply
trusts a role claim injected as a request header. Keeping role resolution in a
single dependency means a future issuer change (e.g. Cognito) would be contained
here rather than spread across handlers — but that is out of scope for the POC.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Header, HTTPException

from mock_lms.config import Settings, get_settings

# Header CloudFront (or a local dev proxy) sets to convey the signed-in role.
ROLE_HEADER = "X-Demo-Role"


class Role(StrEnum):
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


def get_current_role(
    settings: Annotated[Settings, Depends(get_settings)],
    x_demo_role: Annotated[str | None, Header(alias=ROLE_HEADER)] = None,
) -> Role:
    raw = (x_demo_role or settings.default_role).lower()
    try:
        return Role(raw)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=f"Unknown role: {raw!r}") from exc
