"""Synthesis-brief grounding: FM resolves source_payload_paths into a self-contained
source_payloads snapshot so the (separate-store) Field Synthesis service has content."""

from field_mapping.contracts import SynthesisRequestEntry
from field_mapping.service import _ground_synthesis_briefs, _referenced_top_level_keys

_SOURCE = {
    "course": {"name": "Law, Governance & Ethics"},
    "pages": [{"id": "p1", "body": "syllabus"}],
    "modules": [{"name": "Regulatory frameworks"}],
    "unused": {"x": 1},
}


def test_referenced_top_level_keys_tolerates_adhoc_path_syntax() -> None:
    keys = _referenced_top_level_keys(
        ["course.name", "pages[?id='p1'].body", "modules[*].name", "source_payloads.course.x"]
    )
    assert keys == ["course", "pages", "modules"]  # deduped, prefix stripped, order preserved


def test_grounding_snapshots_only_referenced_slices() -> None:
    brief = SynthesisRequestEntry(
        placeholder_id="achievement_description",
        target_path="achievement.description",
        source_payload_paths=["course.name", "pages[*].body"],
        instruction="write it",
    )
    [out] = _ground_synthesis_briefs([brief], _SOURCE)
    assert out.source_payloads is not None
    assert set(out.source_payloads.keys()) == {"course", "pages"}  # not 'unused'/'modules'


def test_grounding_preserves_an_existing_snapshot() -> None:
    brief = SynthesisRequestEntry(
        placeholder_id="d", target_path="a.b", source_payloads={"custom": 1}, instruction="x"
    )
    [out] = _ground_synthesis_briefs([brief], _SOURCE)
    assert out.source_payloads == {"custom": 1}  # §2: provided snapshot is authoritative


def test_grounding_falls_back_to_full_source_when_nothing_resolves() -> None:
    brief = SynthesisRequestEntry(
        placeholder_id="d", target_path="a.b", source_payload_paths=["[?bogus]"], instruction="x"
    )
    [out] = _ground_synthesis_briefs([brief], _SOURCE)
    assert out.source_payloads == _SOURCE
