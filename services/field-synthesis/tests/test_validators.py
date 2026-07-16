from field_synthesis.contracts import SynthesisGeneration
from field_synthesis.validators import validate_generation

_REQUESTED_IDS = {"field_a", "field_b"}


def _gen(
    values: dict[str, str],
    confidence: float | None = 0.85,
    rationale: str | None = "ok",
) -> SynthesisGeneration:
    return SynthesisGeneration(values=values, confidence=confidence, rationale=rationale)


def test_valid_generation_passes() -> None:
    g = _gen({"field_a": "text for a", "field_b": "text for b"})
    assert validate_generation(g, requested_ids=_REQUESTED_IDS) == []


def test_missing_placeholder_fails() -> None:
    g = _gen({"field_a": "text for a"})
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert any("missing" in e for e in errors)
    assert any("field_b" in e for e in errors)


def test_extra_placeholder_fails() -> None:
    g = _gen({"field_a": "text a", "field_b": "text b", "field_c": "extra"})
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert any("unexpected" in e for e in errors)
    assert any("field_c" in e for e in errors)


def test_missing_and_extra_both_reported() -> None:
    g = _gen({"field_a": "text a", "field_c": "wrong key"})
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert len(errors) == 2
    assert any("missing" in e for e in errors)
    assert any("unexpected" in e for e in errors)


def test_confidence_none_fails() -> None:
    g = _gen({"field_a": "a", "field_b": "b"}, confidence=None)
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert any("confidence" in e for e in errors)


def test_rationale_none_fails() -> None:
    g = _gen({"field_a": "a", "field_b": "b"}, rationale=None)
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert any("rationale" in e for e in errors)


def test_both_confidence_and_rationale_none_reports_both() -> None:
    g = _gen({"field_a": "a", "field_b": "b"}, confidence=None, rationale=None)
    errors = validate_generation(g, requested_ids=_REQUESTED_IDS)
    assert any("confidence" in e for e in errors)
    assert any("rationale" in e for e in errors)


def test_empty_values_with_empty_requested_ids_passes() -> None:
    g = _gen({})
    assert validate_generation(g, requested_ids=set()) == []


def test_single_placeholder_passes() -> None:
    g = _gen({"field_a": "some text"})
    assert validate_generation(g, requested_ids={"field_a"}) == []
