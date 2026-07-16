"""Layer-A validation gates for a Field Synthesis generation (design §10).

These are hard gates (ADR-0013 Layer A): a structurally valid response is never a
success on its own (FR-FS-10 / FR-FS-18). ``validate_generation`` returns the list
of validation errors — empty means the generation passed. Invalid generations are
stored as failed artifacts (FR-FS-10), never as successful results.

Grounding (FR-FS-6) is a semantic property evaluated at Layer B using G-Eval; it
cannot be enforced deterministically here.
"""

from __future__ import annotations

from .contracts import SynthesisGeneration


def validate_generation(
    generation: SynthesisGeneration,
    *,
    requested_ids: set[str],
) -> list[str]:
    """Run the §10 hard gates. Returns errors (empty = pass)."""
    errors: list[str] = []
    _check_coverage(generation, requested_ids, errors)
    _check_confidence_and_rationale(generation, errors)
    return errors


def _check_coverage(
    g: SynthesisGeneration, requested_ids: set[str], errors: list[str]
) -> None:
    produced_ids = set(g.values.keys())
    missing = requested_ids - produced_ids
    extra = produced_ids - requested_ids
    if missing:
        errors.append(f"missing placeholder_ids in result: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected placeholder_ids in result: {sorted(extra)}")


def _check_confidence_and_rationale(g: SynthesisGeneration, errors: list[str]) -> None:
    if g.confidence is None:
        errors.append("confidence is absent from model output")
    if g.rationale is None:
        errors.append("rationale is absent from model output")
