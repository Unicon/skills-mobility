"""Generator behavior: determinism + both-variant coverage (assemble→capture model).

Uses a small committed synthetic roster (tests/data/) so the test is hermetic —
the real PM roster CSVs are gitignored input artifacts (design §3).
"""

from pathlib import Path

from mock_lms.catalog import CatalogStore, CourseKind
from mock_lms.generators import generate

DATA = Path(__file__).parent / "data"


def test_same_inputs_are_byte_for_byte_reproducible():
    a = generate(seed=42, csv_dir=DATA)
    b = generate(seed=42, csv_dir=DATA)
    assert a.catalog.model_dump(mode="json") == b.catalog.model_dump(mode="json")


def test_imports_two_course_kinds_from_roster():
    catalog = generate(seed=42, csv_dir=DATA).catalog
    kinds = {c.id: c.kind for c in catalog.courses}
    assert set(kinds.values()) == {CourseKind.STANDARD, CourseKind.DIGITAL_CREDENTIAL}
    # Course names + learner emails come straight from the roster CSVs.
    assert any(c.name == "Introduction to Testing" for c in catalog.courses)
    assert all(u.email for u in catalog.users)


def test_seed_carries_both_variants_of_each_event():
    catalog = generate(seed=42, csv_dir=DATA).catalog

    # skill_mastered: a competency and a sub-competency outcome.
    assert any(o.is_competency for o in catalog.outcomes)
    assert any(not o.is_competency for o in catalog.outcomes)

    # badge_awarded: an accepted/fetchable and an unaccepted badge.
    assert any(b.accepted for b in catalog.badges)
    assert any(not b.accepted for b in catalog.badges)

    # course_completed: a passing and a failing final submission.
    finals = {a.id for a in catalog.assignments if a.role.value == "final"}
    final_scores = [s.score for s in catalog.submissions if s.assignment_id in finals]
    assert any(s is not None and s >= 60 for s in final_scores)
    assert any(s is not None and s < 60 for s in final_scores)


def test_store_resolves_generated_entities():
    catalog = generate(seed=42, csv_dir=DATA).catalog
    store = CatalogStore(catalog)
    standard = next(c for c in catalog.courses if c.kind is CourseKind.STANDARD)

    # Each standard course offers three grading Actions, each on a known assignment.
    actions = store.actions_for(standard.id)
    assert len(actions) == 3
    for action in actions:
        assert store.get_assignment(action.assignment_id) is not None
