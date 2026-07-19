"""Service-specific LearnCard Search Profiles client.

``GET /search/profiles/{input}`` returns an array of profile objects — verified
live in the #41 spike: ``[{"profileId", "did", "displayName", ...}]``. Matching
is on handle/displayName, NOT email. Auth + transport come from the shared
``LearnCardClient`` (libs/learncard-api); the array response means we read
``.json()`` off ``request`` rather than the object-typed ``get``.
"""

from __future__ import annotations

from typing import Any

from learncard_api import LearnCardClient


def search_profiles(client: LearnCardClient, term: str) -> list[dict[str, Any]]:
    resp = client.request("GET", f"/search/profiles/{term}")
    matches: list[dict[str, Any]] = resp.json()
    return matches
