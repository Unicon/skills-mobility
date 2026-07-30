"""Canned access token + deterministic redirect-token derivation (design §2).

The token is a fixed constant (not a random UUID) so tests can import and assert
on it (FR-MSR-5). The redirect token is a stable hash of the recipient + first
credential id so the same inputs always produce the same ``redirect_url``
(FR-MSR-10) — no shared state.
"""

from __future__ import annotations

import hashlib

# Fixed canned access token issued by POST /api/v1/token and required (verbatim)
# as the Bearer token on POST /api/v1/credentials.
CANNED_TOKEN = "mock-smartresume-token"


def derive_redirect_token(recipient_id: str, credential_id: str) -> str:
    """Deterministic 16-char hex identifier from the recipient + credential id."""
    digest = hashlib.sha256(f"{recipient_id}|{credential_id}".encode()).hexdigest()
    return digest[:16]
