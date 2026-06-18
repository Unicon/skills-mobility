# Mock LMS — LMS Resource APIs Requirements

Status: Draft
Date: 2026-06-12
Related: [Mock LMS overview](./README.md) · [Event Producer](./mock-lms-event-producer.md) · [Demo UI](./mock-lms-ui.md) · [Design](../3_design/mock-lms.md) · [POC Requirements](./poc-requirements.md)

## 1. Purpose

The **LMS Resource APIs** are Canvas-style read endpoints that the **Context Builder** queries to assemble decision context (course, enrollment, outcomes, assignments, submissions, rubrics, user profile). Paths and query shapes mirror Canvas so the integration is realistic.

## 2. Endpoints

The producer SHALL expose these read endpoints. Only fields the Context Builder consumes need be populated.

| Purpose | Canvas-style endpoint |
|---|---|
| Get course | `GET /api/v1/courses/{course_id}` |
| Get learner enrollment **+ final grade** | `GET /api/v1/courses/{course_id}/enrollments?user_id={user_id}&type[]=StudentEnrollment&include[]=current_grade&include[]=current_points` |
| Get course modules / static structure | `GET /api/v1/courses/{course_id}/modules?include[]=items` |
| Get pages / static content | `GET /api/v1/courses/{course_id}/pages` and `…/pages/{url}` |
| Get assignments | `GET /api/v1/courses/{course_id}/assignments` |
| Get outcome (skill) details | `GET /api/v1/outcomes/{outcome_id}` |
| Get outcome results | `GET /api/v1/courses/{course_id}/outcome_results?user_ids[]={user_id}&outcome_ids[]={outcome_id}&include[]=alignments` |
| Get outcome-aligned assignments | `GET /api/v1/courses/{course_id}/outcome_alignments?student_id={user_id}` |
| Get learner submissions | `GET /api/v1/courses/{course_id}/students/submissions?student_ids[]={user_id}&assignment_ids[]={assignment_id}` |
| **Get user profile** (email as badge recipient id) | `GET /api/v1/users/{user_id}/profile` |
| **Get course rubrics** (rubric data for badges) | `GET /api/v1/courses/{course_id}/rubrics` |
| **Get badge by id** (POC-defined; Canvas has no equivalent) | `GET /api/v1/badges/{badge_id}` |

New since the first draft (per review): **user profile** (the learner's email is the badge id), **rubrics** (the data people most want inside a badge), the **final grade** include on enrollments (for `course_completed`), and a POC-defined **get badge by id** (the `badge_awarded` flow needs it though Canvas lacks it).

**Deferred** (scope creep for now): Canvas Quizzes / New Quizzes, and Files.

- **FR-API1** Endpoints SHALL be read-only and serve from the seeded data set.
- **FR-API2** Responses SHALL be deterministic — same request → same response — so demos are reproducible.
- **FR-API3** Unknown ids SHALL return Canvas-style `404` shapes; the API SHALL not 500 on missing optional includes.
- **FR-API4** Ids served here SHALL match the ids in emitted event bodies (see [Event Producer §4](./mock-lms-event-producer.md)).

## 3. Data model & repeatability

- **FR-API5** Seed data SHALL use **logically connected identifiers** that resemble a real LMS: a course → its modules → outcomes (skills) → aligned assignments → a learner's submissions → outcome results all reference one another by id, so a viewer can follow the chain.
- **FR-API6** Data SHALL be produced by a **seeded generator** and captured to **committed fixtures** (generate → capture → commit → replay): the generator builds the catalog with deterministic, linked ids; the runtime loads the frozen snapshot read-only and never runs the generator. Same seed → byte-identical data. (Scratch/large generated sets live in gitignored `generated-fixtures/`.)
- **FR-API7** The seed SHALL include both **course kinds** (standard and digital-credential-supported, per [Event Producer §3](./mock-lms-event-producer.md)) and enough learners to demonstrate one-learner vs all-learners Actions.

## 4. Out of scope

- Real Canvas API parity/completeness; writes/mutations; Quizzes/New Quizzes/Files (deferred).
