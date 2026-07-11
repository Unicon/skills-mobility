"""Normalize resolution outcomes into the resolver response (design §2)."""

from __future__ import annotations

from learncard_profile_resolver.schemas import ErrorInfo, ResolvedProfile, ResolveResponse


def stored(profile_id: str, did: str) -> ResolveResponse:
    return ResolveResponse(
        status="succeeded",
        result=ResolvedProfile(profile_id=profile_id, did=did, resolution_method="stored"),
    )


def searched(profile_id: str, did: str) -> ResolveResponse:
    return ResolveResponse(
        status="succeeded",
        result=ResolvedProfile(profile_id=profile_id, did=did, resolution_method="searched"),
    )


def unresolved() -> ResolveResponse:
    return ResolveResponse(status="unresolved")


def error(message: str) -> ResolveResponse:
    return ResolveResponse(status="failed", error=ErrorInfo(message=message))
