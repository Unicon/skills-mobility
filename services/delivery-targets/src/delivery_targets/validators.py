"""Layer-A validation gates for a Delivery Targets selection (design §9).

These are hard gates (ADR-0013 Layer A): a structurally valid response is never a
success on its own (FR-DT-18 / FR-DT-19). ``validate_selection`` returns the list
of validation errors — empty means the selection passed. Invalid selections are
stored as failed artifacts (FR-DT-21), never as successful selections.
"""

from __future__ import annotations

from .contracts import SelectionGeneration


def validate_selection(
    generation: SelectionGeneration,
    *,
    catalog_target_ids: set[str],
) -> list[str]:
    """Run the §9 hard gates. Returns errors (empty = pass)."""
    errors: list[str] = []
    _check_non_empty(generation, errors)
    _check_known_targets(generation, catalog_target_ids, errors)
    _check_no_duplicates(generation, errors)
    _check_confidence_and_rationale(generation, errors)
    return errors


def _check_non_empty(g: SelectionGeneration, errors: list[str]) -> None:
    if not g.selections:
        errors.append("selection list is empty")


def _check_known_targets(
    g: SelectionGeneration, catalog_target_ids: set[str], errors: list[str]
) -> None:
    for sel in g.selections:
        if sel.delivery_target not in catalog_target_ids:
            errors.append(
                f"unknown delivery target '{sel.delivery_target}' (not in catalog)"
            )


def _check_no_duplicates(g: SelectionGeneration, errors: list[str]) -> None:
    seen: set[str] = set()
    for sel in g.selections:
        if sel.delivery_target in seen:
            errors.append(f"duplicate delivery target '{sel.delivery_target}'")
        seen.add(sel.delivery_target)


def _check_confidence_and_rationale(g: SelectionGeneration, errors: list[str]) -> None:
    for sel in g.selections:
        if not (0.0 <= sel.confidence <= 1.0):
            errors.append(
                f"confidence for '{sel.delivery_target}' is out of range: {sel.confidence}"
            )
        if not sel.rationale.strip():
            errors.append(f"rationale for '{sel.delivery_target}' is empty")
