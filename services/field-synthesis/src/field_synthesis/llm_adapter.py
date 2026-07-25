"""The LLM adapter boundary for Field Synthesis.

Both the deterministic replay adapter and the Bedrock adapter implement this one
protocol (FR-FS-27/28), so the service pipeline is identical in test and live
modes — only the adapter swaps.
"""

from __future__ import annotations

from typing import Protocol

from .contracts import LlmCallMeta, SynthesisBrief, SynthesisGeneration, SynthesisRequest


class LLMAdapter(Protocol):
    def generate(
        self, request: SynthesisRequest, *, briefs: list[SynthesisBrief]
    ) -> tuple[SynthesisGeneration, LlmCallMeta]:
        """Produce one synthesis generation for the request (exactly one attempt),
        with the model-call metadata captured for the invocation log (ADR-0010 §60)."""
        ...
