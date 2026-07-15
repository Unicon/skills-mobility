"""The LLM adapter boundary.

Both the deterministic replay adapter and the Bedrock adapter implement this one
protocol (FR-DT-30/31), so the service pipeline is identical in test and live
modes — only the adapter swaps.
"""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import SelectionGeneration, SelectionRequest


class LLMAdapter(Protocol):
    def select(
        self, request: SelectionRequest, *, catalog: list[dict[str, Any]]
    ) -> SelectionGeneration:
        """Produce one selection generation for the request (exactly one attempt)."""
        ...
