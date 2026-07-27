"""Minimal prompt-injection screen for source payloads (FR-FM-27b, ADR-0021).

A lightweight, deterministic scan of the free-text string values in
``source_payloads`` for common prompt-injection phrasings before they are placed
in a Bedrock prompt. This is the "adopt now, minimally" posture from ADR-0021 —
it flags suspicious content (returned as findings for logging), it is not a
guarantee against adversarial input.
"""

from __future__ import annotations

import re
from typing import Any

# Common injection phrasings. Deterministic and intentionally conservative.
_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(system|previous|above)", re.IGNORECASE),
    re.compile(r"\bsystem\s+prompt\b", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"</?(system|assistant|user)>", re.IGNORECASE),
]


class Finding:
    """A single injection-screen hit: the payload path and the matched text."""

    def __init__(self, path: str, snippet: str) -> None:
        self.path = path
        self.snippet = snippet

    def __repr__(self) -> str:
        return f"Finding(path={self.path!r}, snippet={self.snippet!r})"


def screen_for_injection(source_payloads: dict[str, Any]) -> list[Finding]:
    """Walk the payloads and return a finding for each free-text value that matches
    an injection pattern. Empty list means nothing suspicious was seen."""
    findings: list[Finding] = []
    _walk(source_payloads, "source_payloads", findings)
    return findings


def _walk(value: Any, path: str, findings: list[Finding]) -> None:
    if isinstance(value, str):
        for pattern in _PATTERNS:
            match = pattern.search(value)
            if match:
                findings.append(Finding(path, match.group(0)))
                break
    elif isinstance(value, dict):
        for key, child in value.items():
            _walk(child, f"{path}.{key}", findings)
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _walk(child, f"{path}[{i}]", findings)
