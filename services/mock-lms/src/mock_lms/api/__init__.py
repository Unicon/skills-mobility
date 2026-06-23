"""Dependency providers and routers for the Mock LMS API."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from mock_lms.catalog import CatalogStore
from mock_lms.emitter import Emitter


def get_store(request: Request) -> CatalogStore:
    return cast(CatalogStore, request.app.state.store)


def get_emitter(request: Request) -> Emitter:
    return cast(Emitter, request.app.state.emitter)
