"""Dependency providers and routers for the Mock LMS API."""

from __future__ import annotations

from typing import cast

from fastapi import Request

from mock_lms.emission import EmissionLog, Emitter
from mock_lms.scenarios import ScenarioStore


def get_store(request: Request) -> ScenarioStore:
    return cast(ScenarioStore, request.app.state.store)


def get_emitter(request: Request) -> Emitter:
    return cast(Emitter, request.app.state.emitter)


def get_emission_log(request: Request) -> EmissionLog:
    return cast(EmissionLog, request.app.state.emission_log)
