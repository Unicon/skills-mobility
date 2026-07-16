"""Pydantic models mirroring the SmartResume API shapes (design §2).

Only the fields the mock validates or returns are modeled; the credentials body
is otherwise accepted permissively.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600


class Recipient(BaseModel):
    id: str


class CredentialsRequest(BaseModel):
    recipient: Recipient
    credentials: list[dict[str, Any]]


class CredentialsResponse(BaseModel):
    redirect_url: str
