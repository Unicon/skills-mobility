"""GET /healthz — health check (design §3). Always 200, no dependency checks."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
