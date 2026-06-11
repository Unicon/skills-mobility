"""Build a Catalog + Scenarios from a fixed seed.

Design choices that keep the output useful AND reproducible:

- **Ids are deterministic sequences** (course 1001.., learner 2001..,
  outcome 3001.., assignment 4001..), not random — so the Canvas-style APIs and
  the scenario references are stable across regenerations and easy to eyeball.
- **Content is Faker-driven** (names, course/outcome titles, descriptions,
  dates, grades), seeded so it reproduces exactly.
- **The primary learner+course is guaranteed a happy path**: a mastered outcome
  result and a graded, passing submission — so the canonical scenarios always
  demonstrate mastery regardless of seed.
- **No wall-clock**: dates come from Faker within a fixed window, so regenerating
  in CI yields byte-identical fixtures (for a pinned Faker version).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from faker import Faker

from mock_lms.scenarios import (
    Assignment,
    Catalog,
    Course,
    Enrollment,
    EventSpec,
    Module,
    ModuleItem,
    Outcome,
    OutcomeAlignment,
    OutcomeResult,
    Page,
    Scenario,
    Student,
    Submission,
)

# Fixed date window — keeps generation independent of the wall clock.
_WINDOW_START = datetime(2026, 1, 13, tzinfo=UTC)
_WINDOW_END = datetime(2026, 6, 1, tzinfo=UTC)

# Curated, credible skill/course topics. Index-based selection (not random) keeps
# generation deterministic AND keeps the primary course a sensible demo subject.
_TOPICS = [
    "Data Analysis",
    "Project Management",
    "Technical Writing",
    "Cloud Architecture",
    "Cybersecurity Fundamentals",
    "Machine Learning",
    "Financial Accounting",
    "User Experience Research",
    "Supply Chain Management",
    "Digital Marketing",
]

_GRADE_BANDS = [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (70, "C"), (0, "D")]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_BANDS:
        if score >= threshold:
            return letter
    return "F"


def _sortable(name: str) -> str:
    parts = name.split()
    return f"{parts[-1]}, {parts[0]}" if len(parts) >= 2 else name


def _login(name: str) -> str:
    parts = [p.lower() for p in name.split() if p.isalpha()]
    return ".".join([parts[0], parts[-1]]) if len(parts) >= 2 else parts[0]


def _course_code(title: str, index: int) -> str:
    initials = "".join(w[0] for w in title.split()[:3]).upper()
    return f"{initials}-{101 + index}"


@dataclass
class GenerationResult:
    catalog: Catalog
    scenarios: list[Scenario]


def generate(seed: int = 42, learners: int = 1, courses: int = 1) -> GenerationResult:
    if learners < 1 or courses < 1:
        raise ValueError("learners and courses must each be >= 1")

    fake = Faker("en_US")
    fake.seed_instance(seed)

    students: list[Student] = []
    for j in range(learners):
        name = fake.name()
        students.append(
            Student(
                id=str(2001 + j),
                name=name,
                sortable_name=_sortable(name),
                login_id=_login(name),
            )
        )

    catalog = Catalog(students=students)
    scenarios: list[Scenario] = []
    enr_n = sub_n = res_n = 0

    for i in range(courses):
        cid = str(1001 + i)
        oid = str(3001 + i)
        aid = str(4001 + i)
        mid = str(5001 + i)
        align_id = str(8001 + i)

        topic = _TOPICS[i % len(_TOPICS)]
        course_name = f"Introduction to {topic}"
        outcome_title = topic
        assignment_name = f"Final {topic} Project"

        catalog.courses.append(
            Course(id=cid, name=course_name, course_code=_course_code(course_name, i))
        )
        catalog.outcomes.append(
            Outcome(
                id=oid,
                title=outcome_title,
                display_name=f"Apply core concepts and techniques in {topic.lower()}",
                description=(
                    f"Learner can independently apply {topic.lower()} to analyze a problem "
                    "and draw valid, well-supported conclusions."
                ),
                mastery_points=3.0,
                points_possible=5.0,
            )
        )
        due_at = fake.date_time_between(_WINDOW_START, _WINDOW_END, tzinfo=UTC)
        catalog.assignments.append(
            Assignment(
                id=aid,
                course_id=cid,
                name=assignment_name,
                description=(
                    f"Apply {topic.lower()} to a provided real-world dataset and present findings."
                ),
                points_possible=100.0,
                due_at=due_at,
            )
        )
        catalog.pages.append(
            Page(
                course_id=cid,
                url="syllabus",
                title="Course Syllabus",
                body=(
                    f"This course introduces the foundations of {topic}, culminating in a final "
                    f"project assessed against the {topic} outcome."
                ),
            )
        )
        catalog.modules.append(
            Module(
                id=mid,
                course_id=cid,
                name=f"Module 1: Foundations of {topic}",
                position=1,
                items=[
                    ModuleItem(id=f"{mid}01", title="Course Syllabus", type="Page",
                               content_id="syllabus"),
                    ModuleItem(id=f"{mid}02", title=assignment_name, type="Assignment",
                               content_id=aid),
                ],
            )
        )
        catalog.outcome_alignments.append(
            OutcomeAlignment(id=align_id, course_id=cid, outcome_id=oid, assignment_id=aid,
                             name=assignment_name)
        )

        for j, student in enumerate(students):
            is_primary = i == 0 and j == 0
            enr_n += 1
            catalog.enrollments.append(
                Enrollment(id=str(9000 + enr_n), course_id=cid, user_id=student.id)
            )

            submitted = fake.date_time_between(_WINDOW_START, due_at, tzinfo=UTC)
            graded = fake.date_time_between(submitted, _WINDOW_END, tzinfo=UTC)
            score = 95.0 if is_primary else float(fake.random_int(68, 99))
            sub_n += 1
            catalog.submissions.append(
                Submission(
                    id=str(6000 + sub_n),
                    course_id=cid,
                    assignment_id=aid,
                    user_id=student.id,
                    score=score,
                    grade=_grade(score),
                    workflow_state="graded",
                    submitted_at=submitted,
                    graded_at=graded,
                )
            )

            mastery = True if is_primary else fake.boolean(chance_of_getting_true=65)
            outcome_score = 5.0 if mastery else float(fake.random_int(1, 2))
            res_n += 1
            catalog.outcome_results.append(
                OutcomeResult(
                    id=str(7000 + res_n),
                    course_id=cid,
                    user_id=student.id,
                    outcome_id=oid,
                    assignment_id=aid,
                    score=outcome_score,
                    possible=5.0,
                    mastery=mastery,
                    submitted_or_assessed_at=graded,
                )
            )

    scenarios = _build_scenarios(catalog)
    return GenerationResult(catalog=catalog, scenarios=scenarios)


def _build_scenarios(catalog: Catalog) -> list[Scenario]:
    """Three canonical happy paths, bound to the primary learner + course."""
    course = catalog.courses[0]
    learner = catalog.students[0]
    outcome = catalog.outcomes[0]
    assignment = catalog.assignments[0]
    who = learner.name
    return [
        Scenario(
            id="skill-mastered",
            title="Skill Mastered",
            description=(
                f"{who} masters the {outcome.title} outcome on the {assignment.name}; "
                "emits learning_outcome_result_created."
            ),
            events=[
                EventSpec(
                    event_type="skill_mastered",
                    user_id=learner.id,
                    course_id=course.id,
                    outcome_id=outcome.id,
                    assignment_id=assignment.id,
                )
            ],
        ),
        Scenario(
            id="course-completed",
            title="Course Completed",
            description=f"{who} completes {course.name}; emits course_completed.",
            events=[
                EventSpec(event_type="course_completed", user_id=learner.id, course_id=course.id)
            ],
        ),
        Scenario(
            id="badge-awarded",
            title="Badge Awarded",
            description=f"{who} is awarded the {outcome.title} badge; emits badge_awarded.",
            events=[
                EventSpec(
                    event_type="badge_awarded",
                    user_id=learner.id,
                    course_id=course.id,
                    outcome_id=outcome.id,
                    badge_id=f"badge-{outcome.id}",
                    badge_name=outcome.title,
                )
            ],
        ),
    ]
