# Mock LMS — LMS Resource APIs Requirements

Status: Draft
Date: 2026-06-12
Related: [Mock LMS overview](./README.md) · [Event Producer](./mock-lms-event-producer.md) · [Demo UI](./mock-lms-ui.md) · [Design](../3_design/mock-lms.md) · [POC Requirements](./poc-requirements.md)

## 1. Purpose

The **LMS Resource APIs** are Canvas-style read endpoints that the **Context Builder** queries to assemble decision context (course, enrollment, outcomes, assignments, submissions, rubrics, user profile). Paths and query shapes mirror Canvas so the integration is realistic.

## 2. Endpoints

The producer SHALL expose these read endpoints. Only fields the current POC consumers need be populated.

| Purpose | Canvas-style endpoint | Used by | Context Builder event profiles |
|---|---|---|---|
| Get course | `GET /api/v1/courses/{course_id}` | Both | `course_completed` |
| Get learner enrollment **+ final grade** | `GET /api/v1/courses/{course_id}/enrollments?user_id={user_id}&type[]=StudentEnrollment&include[]=current_grade&include[]=current_points` | Context Builder | `course_completed` |
| Get course modules / static structure | `GET /api/v1/courses/{course_id}/modules?include[]=items` | Both | `skill_mastered`, `course_completed` |
| Get pages / static content | `GET /api/v1/courses/{course_id}/pages` | Both | `course_completed` |
| Get page by id | `GET /api/v1/courses/{course_id}/pages/{page_id}` | Context Builder | `skill_mastered` |
| Get assignments for a course | `GET /api/v1/courses/{course_id}/assignments` | Both | `course_completed` |
| Get single assignment | `GET /api/v1/courses/{course_id}/assignments/{assignment_id}` | Context Builder | `skill_mastered` |
| Get outcome (skill) details | `GET /api/v1/outcomes/{outcome_id}` | Both | `skill_mastered` |
| Get learner submissions for a course | `GET /api/v1/courses/{course_id}/students/submissions?student_ids[]={user_id}&include[]=rubric_assessment` | Both | `course_completed` |
| Get learner submission for one assignment | `GET /api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/{user_id}?include[]=rubric_assessment` | Both | `skill_mastered` |
| Get account user by Canvas user UUID | `GET /api/v1/accounts/{account_id}/users?uuids[]={canvas_user_uuid}` | Context Builder | `skill_mastered` |
| **Get user profile** (email as badge recipient id) | `GET /api/v1/users/{user_id}/profile` | Both | `course_completed`, `badge_awarded` |
| **Get course rubrics** | `GET /api/v1/courses/{course_id}/rubrics` | Both | `course_completed` |
| **Get rubric by id** | `GET /api/v1/courses/{course_id}/rubrics/{rubric_id}` | Context Builder | `skill_mastered` |
| **Get badge by id** (POC-defined; Canvas has no equivalent) | `GET /api/v1/badges/{badge_id}` | Context Builder | `badge_awarded` |

The current contract intentionally omits endpoints that no current POC consumer depends on. In particular, the current Context Builder recipes no longer use `outcome_results` or `outcome_alignments`. The `pages/{page_id}` endpoint (above) is the preferred path for the `skill_mastered` module-page fetch; fetching the full pages list and filtering by id is an acceptable fallback.

New since the first draft (per review): **user profile** (the learner's email is the badge id), **rubrics** (the data people most want inside a badge), the **final grade** include on enrollments (for `course_completed`), and a POC-defined **get badge by id** (the `badge_awarded` flow needs it though Canvas lacks it).

**Deferred** (scope creep for now): Canvas Quizzes / New Quizzes, and Files.

- **FR-API1** Endpoints SHALL be read-only and serve from the seeded data set.
- **FR-API2** Responses SHALL be deterministic — same request → same response — so demos are reproducible.
- **FR-API3** Unknown ids SHALL return Canvas-style `404` shapes; the API SHALL not 500 on missing optional includes.
- **FR-API4** Ids served here SHALL match the identifiers carried in emitted event metadata and bodies that the Context Builder relies on (see [Event Producer §4](./mock-lms-event-producer.md)).

## 3. Data model & repeatability

- **FR-API5** Seed data SHALL use **logically connected identifiers** that resemble a real LMS: a course → its modules → outcomes (skills) → assignments → rubrics → learner profile/enrollment/submissions all reference one another by id, so a viewer can follow the chain.
- **FR-API6** Data SHALL be produced by a **seeded generator** and captured to **committed fixtures** (generate → capture → commit → replay): the generator builds the catalog with deterministic, linked ids; the runtime loads the frozen snapshot read-only and never runs the generator. Same seed → byte-identical data. (Scratch/large generated sets live in gitignored `generated-fixtures/`.)
- **FR-API7** The seed SHALL include both **course kinds** (standard and digital-credential-supported, per [Event Producer §3](./mock-lms-event-producer.md)) and enough learners to demonstrate one-learner vs all-learners Actions.

## 4. Out of scope

- Real Canvas API parity/completeness; writes/mutations; Quizzes/New Quizzes/Files (deferred).
