from delivery_targets.contracts import SelectionGeneration, TargetSelection
from delivery_targets.validators import validate_selection

_CATALOG_IDS = {"learncard_issuer", "learncard_wallet", "smart_resume"}


def _gen(*targets: tuple[str, float, str]) -> SelectionGeneration:
    return SelectionGeneration(
        selections=[
            TargetSelection(delivery_target=t, confidence=c, rationale=r)
            for t, c, r in targets
        ]
    )


def test_valid_selection_passes() -> None:
    g = _gen(("learncard_issuer", 0.95, "credential course"), ("learncard_wallet", 0.90, "wallet"))
    assert validate_selection(g, catalog_target_ids=_CATALOG_IDS) == []


def test_empty_selection_fails() -> None:
    g = SelectionGeneration(selections=[])
    errors = validate_selection(g, catalog_target_ids=_CATALOG_IDS)
    assert any("empty" in e for e in errors)


def test_unknown_target_fails() -> None:
    g = _gen(("bogus_system", 0.9, "some rationale"))
    errors = validate_selection(g, catalog_target_ids=_CATALOG_IDS)
    assert any("unknown delivery target" in e for e in errors)


def test_duplicate_target_fails() -> None:
    g = _gen(
        ("learncard_issuer", 0.95, "first"),
        ("learncard_issuer", 0.80, "duplicate"),
    )
    errors = validate_selection(g, catalog_target_ids=_CATALOG_IDS)
    assert any("duplicate" in e for e in errors)


def test_confidence_out_of_range_fails() -> None:
    g = _gen(("learncard_issuer", 1.5, "overconfident"))
    errors = validate_selection(g, catalog_target_ids=_CATALOG_IDS)
    assert any("out of range" in e for e in errors)


def test_empty_rationale_fails() -> None:
    g = _gen(("learncard_issuer", 0.9, "   "))
    errors = validate_selection(g, catalog_target_ids=_CATALOG_IDS)
    assert any("rationale" in e and "empty" in e for e in errors)


def test_single_smart_resume_passes() -> None:
    g = _gen(("smart_resume", 0.88, "non-credential course"))
    assert validate_selection(g, catalog_target_ids=_CATALOG_IDS) == []


def test_all_three_targets_passes() -> None:
    g = _gen(
        ("learncard_issuer", 0.95, "r1"),
        ("learncard_wallet", 0.90, "r2"),
        ("smart_resume", 0.80, "r3"),
    )
    assert validate_selection(g, catalog_target_ids=_CATALOG_IDS) == []
