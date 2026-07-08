"""Phase-1 OBv3 payload preparation.

This is the Orchestrator's deterministic stand-in for the offloaded Field
Mapping / Field Synthesis / Transformation Executor jobs: build the *minimum*
unsigned Open Badges 3.0 credential the LearnCard Issuer Adapter needs, pulling
the achievement name/description from the context bundle's outcome when present
and embedding the resolved recipient DID in ``credentialSubject.id``.
"""

from __future__ import annotations

import re
from typing import Any

_OBV3_CONTEXT = [
    "https://www.w3.org/ns/credentials/v2",
    "https://purl.imsglobal.org/spec/ob/v3p0/context-3.0.3.json",
]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "achievement"


def build_unsigned_obv3(
    bundle: dict[str, Any], recipient_did: str, issuer_id: str
) -> dict[str, Any]:
    outcome = (bundle.get("source_data", {}) or {}).get("outcome", {}) or {}
    name = outcome.get("display_name") or outcome.get("title") or "Skill Achievement"
    description = outcome.get("description") or "Awarded for demonstrating the achievement."
    return {
        "@context": _OBV3_CONTEXT,
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "issuer": {"id": issuer_id, "type": ["Profile"]},
        "credentialSubject": {
            "id": recipient_did,
            "type": ["AchievementSubject"],
            "achievement": {
                "id": f"urn:poc:achievement:{_slug(name)}",
                "type": ["Achievement"],
                "name": name,
                "description": description,
            },
        },
    }


def prepare_wallet_input(
    signed_credential: dict[str, Any], recipient_profile_id: str
) -> dict[str, Any]:
    """Adjust the issued credential into the wallet-delivery payload shape."""
    return {"recipient_profile_id": recipient_profile_id, "signed_credential": signed_credential}
