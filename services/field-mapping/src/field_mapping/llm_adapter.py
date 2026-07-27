"""The LLM adapter boundary.

Both the deterministic replay adapter and the future Bedrock adapter implement
this one protocol (FR-FM-31/32), so the service pipeline is identical in test and
live modes — only the adapter swaps.
"""

from __future__ import annotations

from typing import Any, Protocol

from .contracts import LlmCallMeta, MappingGeneration, MappingRequest


class LLMAdapter(Protocol):
    def generate(
        self,
        request: MappingRequest,
        *,
        target_schema: dict[str, Any],
        source_catalogs: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[MappingGeneration, LlmCallMeta]:
        """Produce one mapping generation for the request (exactly one attempt),
        with the model-call metadata captured for the invocation log (ADR-0010 §60).
        ``source_catalogs`` contains the resolved source-field catalog schemas keyed
        by source-payload alias (design §7); adapters that do not use them accept and
        ignore this parameter."""
        ...
