"""The LLM adapter boundary (design §12).

Both the deterministic replay adapter and the Bedrock adapter implement this
Protocol, so the service pipeline is identical in test and live modes —
only the adapter swaps.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import GateGeneration, GateRequest, PlanGeneration, PlanRequest


class LLMAdapter(Protocol):
    def gate(
        self, request: GateRequest, *, gating_prose: str
    ) -> GateGeneration:
        """Produce a gate generation for the request (exactly one attempt)."""
        ...

    def plan(
        self, request: PlanRequest, *, registry_view: list[dict[str, str]]
    ) -> PlanGeneration:
        """Produce a plan generation for the request (exactly one attempt)."""
        ...
