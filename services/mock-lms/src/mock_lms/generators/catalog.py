"""Assemble the Mock LMS catalog: real roster CSV subset + generated layer.

Design §3 (generate → capture → commit → replay). Two sources:

1. **Real roster base** — a small, deterministic subset of the PM's Canvas
   SIS-style exports (``course_sections.csv``, ``users.csv``, ``enrollments.csv``)
   gives realistic courses, learners (with real emails), and enrollments.
2. **Generated academic/credential layer** — the CSVs lack the activity/credential
   data our events need, so we generate modules, outcomes (competency +
   sub-competency), module + final assignments, submissions (passing + failing),
   outcome results, rubrics, and badges (accepted + unaccepted) on top.

Determinism: course/learner selection is sorted (not random); ids are derived
from stable business keys; Faker (seeded) fills only free text and dates within a
fixed window. Same CSVs + seed + Faker version → byte-identical fixtures.

The raw CSVs are input artifacts (kept out of the repo); only the captured
``catalog.json`` is committed and loaded at runtime.
"""

from __future__ import annotations

import csv
import uuid as uuidlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from faker import Faker

from mock_lms.catalog import (
    Action,
    Assignment,
    AssignmentRole,
    Badge,
    Catalog,
    Course,
    CourseKind,
    Enrollment,
    Module,
    ModuleItem,
    Outcome,
    OutcomeResult,
    Page,
    Rubric,
    RubricCriterion,
    RubricRating,
    Submission,
    SubmissionCriterionAssessment,
    User,
)
from mock_lms.generators.content import SubjectContent, content_for

# Fixed date window — keeps generation independent of the wall clock.
_WINDOW_START = datetime(2026, 1, 13, tzinfo=UTC)
_WINDOW_END = datetime(2026, 5, 1, tzinfo=UTC)

# Defaults for how much of the roster to pull into the demo. Both are adjustable
# via the generator CLI (``--courses`` / ``--learners-per-course``) and are capped
# by what the roster actually contains.
_DEFAULT_COURSES = 6
_DEFAULT_LEARNERS_PER_COURSE = 6

# Passing / failing final scores for the seeded course_completed variants.
_PASS_SCORE = 92.0
_FAIL_SCORE = 52.0

_GRADE_BANDS = [(93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (70, "C"), (60, "D")]


def _grade(score: float) -> str:
    for threshold, letter in _GRADE_BANDS:
        if score >= threshold:
            return letter
    return "F"


def _user_uuid(user_id: str) -> str:
    """Deterministic Canvas-style UUID derived from the user id (no wall clock,
    no RNG — keeps fixtures byte-identical)."""
    return str(uuidlib.uuid5(uuidlib.NAMESPACE_URL, f"mock-lms/user/{user_id}"))


def _sortable(name: str) -> str:
    parts = name.split()
    return f"{parts[-1]}, {parts[0]}" if len(parts) >= 2 else name


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class GenerationResult:
    catalog: Catalog


# --- Roster subset selection ------------------------------------------------


@dataclass
class _RosterCourse:
    course_id: str
    section_id: str
    name: str
    institution: str
    term: str
    learners: list[User]


def _profile(row: dict[str, str]) -> dict[str, str]:
    """Non-empty ``property:*`` columns from a users.csv row, key without prefix."""
    out: dict[str, str] = {}
    for key, value in row.items():
        if key.startswith("property:") and value:
            out[key.removeprefix("property:")] = value
    return out


def _roster_course(
    course_id: str,
    sections: list[dict[str, str]],
    users: dict[str, dict[str, str]],
    enrollments: list[dict[str, str]],
    learners_per_course: int,
) -> _RosterCourse | None:
    """Build one ``_RosterCourse`` from its first section, or ``None`` if no
    enrolled student rows resolve (so such courses are skipped, not fatal)."""
    section = min(r["section_id"] for r in sections if r["course_id"] == course_id)
    row = next(r for r in sections if r["section_id"] == section)
    student_ids = sorted(
        e["user_id"]
        for e in enrollments
        if e["section_id"] == section and e["role"] == "student"
    )
    learners: list[User] = []
    for uid in student_ids:
        urow = users.get(uid)
        if urow is None:
            continue
        learners.append(
            User(
                id=uid,
                uuid=_user_uuid(uid),
                name=urow["full_name"],
                sortable_name=_sortable(urow["full_name"]),
                login_id=urow["login_id"],
                email=urow["email"],
                profile=_profile(urow),
            )
        )
        if len(learners) >= learners_per_course:
            break
    if not learners:
        return None
    return _RosterCourse(
        course_id=course_id,
        section_id=section,
        name=row["name"],
        institution=row.get("property:Institution", ""),
        term=row.get("property:Term", ""),
        learners=learners,
    )


def _select_roster(
    csv_dir: Path, n_courses: int, learners_per_course: int
) -> list[tuple[CourseKind, _RosterCourse]]:
    """Pick demo courses + their learners deterministically from the roster.

    Up to ``n_courses`` distinct course ids (sorted) are selected, each with up
    to ``learners_per_course`` enrolled students from its first section. Kinds
    are split ~2:1 standard:digital-credential with at least one of each, so the
    demo always carries both course kinds (and therefore every event variant).
    """
    sections = _read_csv(csv_dir / "course_sections.csv")
    users = {r["user_id"]: r for r in _read_csv(csv_dir / "users.csv")}
    enrollments = _read_csv(csv_dir / "enrollments.csv")

    course_ids = sorted({r["course_id"] for r in sections})
    if len(course_ids) < 2:
        raise ValueError("roster needs at least two distinct courses")

    rosters: list[_RosterCourse] = []
    for course_id in course_ids:
        if len(rosters) >= n_courses:
            break
        rc = _roster_course(course_id, sections, users, enrollments, learners_per_course)
        if rc is not None:
            rosters.append(rc)
    if len(rosters) < 2:
        raise ValueError("roster yielded fewer than two courses with enrolled learners")

    # ~2:1 standard:digital-credential, guaranteeing at least one of each.
    n_digital = max(1, len(rosters) // 3)
    n_standard = len(rosters) - n_digital
    kinds = [CourseKind.STANDARD] * n_standard + [CourseKind.DIGITAL_CREDENTIAL] * n_digital
    return list(zip(kinds, rosters, strict=True))


# --- Generation -------------------------------------------------------------


def generate(
    seed: int = 42,
    csv_dir: Path | None = None,
    n_courses: int = _DEFAULT_COURSES,
    learners_per_course: int = _DEFAULT_LEARNERS_PER_COURSE,
) -> GenerationResult:
    csv_dir = csv_dir or _default_csv_dir()
    fake = Faker("en_US")
    fake.seed_instance(seed)

    catalog = Catalog()
    for kind, rc in _select_roster(csv_dir, n_courses, learners_per_course):
        course = Course(
            id=rc.course_id,
            name=rc.name,
            course_code=rc.course_id,
            kind=kind,
            institution=rc.institution,
            term=rc.term,
        )
        catalog.courses.append(course)
        catalog.users.extend(rc.learners)
        for learner in rc.learners:
            catalog.enrollments.append(
                Enrollment(
                    id=f"{rc.course_id}-ENR-{learner.id}",
                    course_id=rc.course_id,
                    user_id=learner.id,
                )
            )
        if kind is CourseKind.STANDARD:
            _generate_standard(catalog, course, rc, fake)
        else:
            _generate_digital_credential(catalog, course, rc, fake)

    return GenerationResult(catalog=catalog)


def _due(fake: Faker) -> datetime:
    return fake.date_time_between(_WINDOW_START, _WINDOW_END, tzinfo=UTC)


def _rubric(course_id: str, assignment_id: str, title: str, content: SubjectContent) -> Rubric:
    """Subject-specific rubric (issue #23): real, varied criteria + ratings."""
    return Rubric(
        id=f"{course_id}-RUB-{assignment_id}",
        course_id=course_id,
        assignment_id=assignment_id,
        title=f"{title} Rubric",
        criteria=[
            RubricCriterion(
                id=f"{assignment_id}-{c.key}",
                description=c.description,
                points=c.points,
                ratings=[RubricRating(description=d, points=p) for d, p in c.ratings],
            )
            for c in content.rubric_criteria
        ],
    )


def _rubric_assessment(
    rubric: Rubric, content: SubjectContent, passed: bool, variation: int
) -> list[SubmissionCriterionAssessment]:
    """Per-criterion assessment for a submission — top rating when the learner
    met the standard, a lower one otherwise (Canvas ``rubric_assessment``)."""
    out: list[SubmissionCriterionAssessment] = []
    for i, crit in enumerate(rubric.criteria):
        rating = crit.ratings[0] if passed else crit.ratings[min(1, len(crit.ratings) - 1)]
        comment = content.grader_comments[(variation + i) % len(content.grader_comments)]
        out.append(
            SubmissionCriterionAssessment(
                criterion_id=crit.id,
                points=rating.points,
                rating_description=rating.description,
                comments=comment,
            )
        )
    return out


def _graded_submission(
    course_id: str,
    assignment_id: str,
    user_id: str,
    score: float,
    fake: Faker,
    *,
    rubric: Rubric,
    content: SubjectContent,
    variation: int,
) -> Submission:
    submitted = fake.date_time_between(_WINDOW_START, _WINDOW_END, tzinfo=UTC)
    graded = fake.date_time_between(submitted, _WINDOW_END, tzinfo=UTC)
    passed = score >= _PASS_SCORE
    return Submission(
        id=f"{course_id}-SUB-{assignment_id}-{user_id}",
        course_id=course_id,
        assignment_id=assignment_id,
        user_id=user_id,
        score=score,
        grade=_grade(score),
        workflow_state="graded",
        body=content.submission_bodies[variation % len(content.submission_bodies)],
        rubric_assessment=_rubric_assessment(rubric, content, passed, variation),
        submitted_at=submitted,
        graded_at=graded,
    )


def _generate_standard(catalog: Catalog, course: Course, rc: _RosterCourse, fake: Faker) -> None:
    cid = course.id
    subject = course.name.removeprefix("Introduction to ").strip() or course.name

    # Outcome-title convention: a competency is "N.0.0" (an integer then all
    # zeros); a sub-competency is "N.M.0" (a second non-zero segment). The
    # skill_mastered event carries the title, so the happy (competency) vs edge
    # (sub-competency) split is inferable from the event alone.
    competency = Outcome(
        id=f"{cid}-OUT-1",
        title=f"1.0.0 {subject} Principles",
        display_name=f"Apply core principles of {subject.lower()}",
        description=f"Learner can independently apply {subject.lower()} to analyze a problem.",
        code="1.0.0",
    )
    sub_competency = Outcome(
        id=f"{cid}-OUT-1-2",
        title=f"1.2.0 Prepare a {subject.lower()} work product",
        display_name=f"Complete a discrete {subject.lower()} task",
        description=f"Learner can complete a single bounded {subject.lower()} task accurately.",
        code="1.2.0",
    )
    catalog.outcomes.extend([competency, sub_competency])

    a_m1 = Assignment(
        id=f"{cid}-A-M1",
        course_id=cid,
        name="Module 1 Assessment",
        description=f"Demonstrate the {subject} competency.",
        due_at=_due(fake),
        role=AssignmentRole.MODULE,
        module_id=f"{cid}-MOD-1",
        outcome_id=competency.id,
    )
    a_m2 = Assignment(
        id=f"{cid}-A-M2",
        course_id=cid,
        name="Module 2 Assessment",
        description=f"Demonstrate a {subject} sub-skill.",
        due_at=_due(fake),
        role=AssignmentRole.MODULE,
        module_id=f"{cid}-MOD-2",
        outcome_id=sub_competency.id,
    )
    a_final = Assignment(
        id=f"{cid}-A-FINAL",
        course_id=cid,
        name=f"Final {subject} Exam",
        description=f"Comprehensive {subject} assessment.",
        due_at=_due(fake),
        role=AssignmentRole.FINAL,
    )
    catalog.assignments.extend([a_m1, a_m2, a_final])
    catalog.modules.extend(
        [
            Module(
                id=f"{cid}-MOD-1",
                course_id=cid,
                name=f"Module 1: Foundations of {subject}",
                position=1,
                items=[ModuleItem(id=f"{cid}-MOD-1-I1", title=a_m1.name, type="Assignment",
                                  content_id=a_m1.id)],
            ),
            Module(
                id=f"{cid}-MOD-2",
                course_id=cid,
                name=f"Module 2: Applying {subject}",
                position=2,
                items=[ModuleItem(id=f"{cid}-MOD-2-I1", title=a_m2.name, type="Assignment",
                                  content_id=a_m2.id)],
            ),
        ]
    )
    catalog.pages.append(
        Page(id=f"{cid}-PAGE-syllabus", course_id=cid, url="syllabus", title="Course Syllabus",
             body=f"Foundations of {subject}, assessed across two modules and a final.")
    )
    content = content_for(course.course_code)
    rubrics = {a.id: _rubric(cid, a.id, a.name, content) for a in (a_m1, a_m2, a_final)}
    for a in (a_m1, a_m2, a_final):
        a.rubric_id = rubrics[a.id].id
    catalog.rubrics.extend(rubrics.values())

    # Learner work: first learner passes, second fails, rest pass — so the final
    # Action can demonstrate both the passing and failing course_completed variant.
    for idx, learner in enumerate(rc.learners):
        final_score = _FAIL_SCORE if idx == 1 else _PASS_SCORE
        for assignment in (a_m1, a_m2, a_final):
            score = final_score if assignment is a_final else _PASS_SCORE
            catalog.submissions.append(
                _graded_submission(
                    cid, assignment.id, learner.id, score, fake,
                    rubric=rubrics[assignment.id], content=content, variation=idx,
                )
            )
        for outcome in (competency, sub_competency):
            catalog.outcome_results.append(
                OutcomeResult(
                    id=f"{cid}-OR-{outcome.id}-{learner.id}",
                    course_id=cid,
                    user_id=learner.id,
                    outcome_id=outcome.id,
                    assignment_id=(a_m1.id if outcome is competency else a_m2.id),
                    score=outcome.points_possible,
                    possible=outcome.points_possible,
                    mastery=True,
                    submitted_or_assessed_at=_WINDOW_END,
                )
            )
        # Record the final grade on the enrollment too (Canvas surfaces it there).
        for e in catalog.enrollments:
            if e.course_id == cid and e.user_id == learner.id:
                e.current_grade = _grade(final_score)
                e.current_points = final_score

    catalog.actions.extend(
        [
            Action(id=f"{cid}-grade-m1", course_id=cid,
                   label="Grade Module 1 (competency outcome)", assignment_id=a_m1.id),
            Action(id=f"{cid}-grade-m2", course_id=cid,
                   label="Grade Module 2 (sub-competency outcome)", assignment_id=a_m2.id),
            Action(id=f"{cid}-grade-final", course_id=cid,
                   label="Grade Final Exam (passing / failing learner)", assignment_id=a_final.id),
        ]
    )


def _generate_digital_credential(
    catalog: Catalog, course: Course, rc: _RosterCourse, fake: Faker
) -> None:
    cid = course.id
    subject = course.name.removeprefix("Introduction to ").strip() or course.name

    competency = Outcome(
        id=f"{cid}-OUT-1",
        title=f"1.0.0 {subject} Competency",
        display_name=f"Demonstrate {subject.lower()} competency",
        description=f"Learner demonstrates {subject.lower()} competency to a credential standard.",
        code="1.0.0",
    )
    catalog.outcomes.append(competency)

    badge_accepted = Badge(
        id=f"{cid}-BADGE-ACCEPTED",
        course_id=cid,
        name=f"{subject} Module Badge",
        description=f"Awarded for demonstrating a {subject.lower()} competency.",
        outcome_id=competency.id,
        criteria=f"Pass the {subject} module assessment.",
        accepted=True,
    )
    badge_unaccepted = Badge(
        id=f"{cid}-BADGE-UNACCEPTED",
        course_id=cid,
        name=f"{subject} Provisional Badge",
        description="Issued by a provider not yet accepted by the wallet.",
        criteria=f"Pass the second {subject} module assessment.",
        accepted=False,
    )
    badge_course = Badge(
        id=f"{cid}-BADGE-COURSE",
        course_id=cid,
        name=f"{subject} Course Credential",
        description=f"Awarded for completing the {subject} course.",
        outcome_id=competency.id,
        criteria=f"Complete the {course.name} capstone.",
        accepted=True,
    )
    catalog.badges.extend([badge_accepted, badge_unaccepted, badge_course])

    a_m1 = Assignment(
        id=f"{cid}-A-M1",
        course_id=cid,
        name="Module 1 Project",
        description=f"Project evidencing a {subject} competency.",
        due_at=_due(fake),
        role=AssignmentRole.MODULE,
        module_id=f"{cid}-MOD-1",
        badge_id=badge_accepted.id,
    )
    a_m2 = Assignment(
        id=f"{cid}-A-M2",
        course_id=cid,
        name="Module 2 Project",
        description=f"Project evidencing a second {subject} competency.",
        due_at=_due(fake),
        role=AssignmentRole.MODULE,
        module_id=f"{cid}-MOD-2",
        badge_id=badge_unaccepted.id,
    )
    a_final = Assignment(
        id=f"{cid}-A-FINAL",
        course_id=cid,
        name=f"{subject} Capstone",
        description=f"Capstone for the {course.name} credential.",
        due_at=_due(fake),
        role=AssignmentRole.FINAL,
        badge_id=badge_course.id,
    )
    catalog.assignments.extend([a_m1, a_m2, a_final])
    catalog.modules.extend(
        [
            Module(id=f"{cid}-MOD-1", course_id=cid, name="Module 1", position=1,
                   items=[ModuleItem(id=f"{cid}-MOD-1-I1", title=a_m1.name, type="Assignment",
                                     content_id=a_m1.id)]),
            Module(id=f"{cid}-MOD-2", course_id=cid, name="Module 2", position=2,
                   items=[ModuleItem(id=f"{cid}-MOD-2-I1", title=a_m2.name, type="Assignment",
                                     content_id=a_m2.id)]),
        ]
    )
    catalog.pages.append(
        Page(id=f"{cid}-PAGE-syllabus", course_id=cid, url="syllabus", title="Course Syllabus",
             body=f"{course.name}: a digital-credential course issuing badges per module.")
    )
    content = content_for(course.course_code)
    rubrics = {a.id: _rubric(cid, a.id, a.name, content) for a in (a_m1, a_m2, a_final)}
    for a in (a_m1, a_m2, a_final):
        a.rubric_id = rubrics[a.id].id
    catalog.rubrics.extend(rubrics.values())

    for assignment in (a_m1, a_m2, a_final):
        for idx, learner in enumerate(rc.learners):
            catalog.submissions.append(
                _graded_submission(
                    cid, assignment.id, learner.id, _PASS_SCORE, fake,
                    rubric=rubrics[assignment.id], content=content, variation=idx,
                )
            )

    catalog.actions.extend(
        [
            Action(id=f"{cid}-grade-m1", course_id=cid,
                   label="Grade Module 1 (accepted/fetchable badge)", assignment_id=a_m1.id),
            Action(id=f"{cid}-grade-m2", course_id=cid,
                   label="Grade Module 2 (unaccepted badge)", assignment_id=a_m2.id),
            Action(id=f"{cid}-grade-final", course_id=cid,
                   label="Grade Capstone (course credential)", assignment_id=a_final.id),
        ]
    )


def _default_csv_dir() -> Path:
    # Gitignored input artifacts (design §3): services/mock-lms/seed-data/.
    # catalog.py → generators → mock_lms → src → services/mock-lms.
    return Path(__file__).resolve().parents[3] / "seed-data"
