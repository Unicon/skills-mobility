"""Load the transient source payloads for a mapping request (§4).

The Orchestrator passes source payloads inline by default; this loader confirms
the payloads the fetch profile requires are present. The optional
payload-by-reference fallback (§4) is not supported yet — inline only.
"""

from __future__ import annotations

from typing import Any

from .contracts import MappingRequest


class MissingSourcePayloadError(Exception):
    """The request omitted one or more source payloads the profile requires."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"missing required source payloads: {', '.join(missing)}")


def load_source_payloads(
    request: MappingRequest, *, required_aliases: list[str]
) -> dict[str, Any]:
    """Return the inline source payloads, asserting the required aliases are present.

    ``required_aliases`` comes from the resolved fetch-profile mapping's
    ``required_aliases`` (conditional resources like ``rubric`` are not required).
    """
    payloads = request.source_payloads
    missing = [alias for alias in required_aliases if alias not in payloads]
    if missing:
        raise MissingSourcePayloadError(missing)
    return payloads
