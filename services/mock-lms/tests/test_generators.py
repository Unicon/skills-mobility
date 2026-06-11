"""Generator behavior: determinism + happy-path invariants (generate→capture model)."""

from mock_lms.generators import generate
from mock_lms.scenarios import ScenarioStore


def test_same_seed_is_byte_for_byte_reproducible():
    a = generate(seed=42, learners=3, courses=2)
    b = generate(seed=42, learners=3, courses=2)
    assert a.catalog.model_dump(mode="json") == b.catalog.model_dump(mode="json")
    assert [s.model_dump(mode="json") for s in a.scenarios] == [
        s.model_dump(mode="json") for s in b.scenarios
    ]


def test_primary_learner_has_guaranteed_happy_path():
    result = generate(seed=7, learners=4, courses=3)
    store = ScenarioStore(result.catalog, result.scenarios)

    # Primary ids are stable regardless of seed.
    assert store.get_course("1001") is not None
    assert store.get_student("2001") is not None
    assert store.get_outcome("3001") is not None
    assert store.get_assignment("4001") is not None

    # The primary learner mastered the primary outcome...
    results = store.outcome_results("1001", user_ids=["2001"], outcome_ids=["3001"])
    assert results and results[0].mastery is True
    # ...and has a graded submission on the primary assignment.
    subs = store.submissions("1001", student_ids=["2001"], assignment_ids=["4001"])
    assert subs and subs[0].workflow_state == "graded" and subs[0].grade


def test_canonical_scenarios_present_and_bound_to_primary():
    result = generate()
    by_id = {s.id: s for s in result.scenarios}
    assert set(by_id) == {"skill-mastered", "course-completed", "badge-awarded"}
    skill = by_id["skill-mastered"].events[0]
    assert (skill.user_id, skill.course_id, skill.outcome_id) == ("2001", "1001", "3001")


def test_scales_to_requested_size():
    result = generate(seed=1, learners=5, courses=2)
    assert len(result.catalog.students) == 5
    assert len(result.catalog.courses) == 2
    # one enrollment/submission/result per (learner, course)
    assert len(result.catalog.enrollments) == 10
    assert len(result.catalog.submissions) == 10
