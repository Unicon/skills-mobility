"""Orchestrator request + execution-trace contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RunRequest(BaseModel):
    """The workflow-start the Event Consumer hands off: the raw event + the
    execution id created at ingress."""

    execution_id: str
    event: dict[str, Any]


class StepTrace(BaseModel):
    """One executed plan step, recorded for the correlated execution view."""

    step: str
    status: str  # "ok" | "stubbed" | "skipped" | "error"
    note: str = ""


class ExecutionRecord(BaseModel):
    """The correlated per-workflow execution record (ADR-0014/0015)."""

    execution_id: str
    event_type: str | None = None
    status: str  # "completed" | "failed"
    steps: list[StepTrace] = []
    result: dict[str, Any] = {}
