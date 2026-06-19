# Mock LMS — Event Producer Requirements

Status: Draft
Date: 2026-06-12
Related: [Mock LMS overview](./README.md) · [LMS APIs](./mock-lms-apis.md) · [Demo UI](./mock-lms-ui.md) · [Design](../3_design/mock-lms.md) · [POC Requirements](./poc-requirements.md) · [ADR-0001](../decisions/0001-repo-structure.md) · [ADR-0003](../decisions/0003-programming-language.md)

## 1. Purpose

The Event Producer publishes **credential-relevant events** onto the POC event bus (Amazon EventBridge), standing in for events a real LMS (Canvas) would emit. It is the entry point that drives the downstream orchestration.

## 2. Events

The producer emits three event types (the POC happy paths):

| Event type | Modeled on (Canvas) |
|---|---|
| `skill_mastered` | `learning_outcome_result_created` |
| `course_completed` | `course_completed` (carries the learner's final course grade) |
| `badge_awarded` | POC-defined |

`credential_eligible` is **not** emitted — there is no realistic source event for it and nothing to mock against. (The parent PRD lists it; that is a noted deviation.)

## 3. Actions (what triggers events)

A demo operator does not emit raw events — they take an **Action** within a course. A **Course contains Actions**; each Action emits one or more events and can target **one learner** or **all enrolled learners** (a bulk Action emits N events of the same type, e.g. "submit final grades for all 200 learners" → 200 `course_completed`).

Two **course kinds** determine which Actions a course offers (a course shows one set, to avoid confusion):

| Course kind | Actions | Event emitted |
|---|---|---|
| **Standard** | Submit final grade (one / all learners) | `course_completed` (×1 / ×N) |
| | Submit skill mastery (one / all learners) | `skill_mastered` (×1 / ×N) |
| **Digital-credential-supported** | Award badge for skill mastery (one / all) | `badge_awarded` (×1 / ×N) |
| | Award badge for course mastery (one / all) | `badge_awarded` (×1 / ×N) |

- **FR-EP1** The producer SHALL publish structured JSON events to the POC event bus.
- **FR-EP2** An Action SHALL emit the event type(s) above; a bulk (all-learners) Action SHALL emit one event per enrolled learner.
- **FR-EP3** Each emitted event SHALL carry a **correlation id** (shared across all events of one Action) so downstream execution traces back to the triggering Action.
- **FR-EP4** Emission SHALL be **idempotency-friendly**: each event carries a unique `event_id`; re-running an Action produces fresh ids over stable business keys (learner, course, outcome), so the demo repeats without colliding with prior runs.
- **FR-EP5** The emission control API SHALL return the emitted envelope(s) and correlation id synchronously to the caller (the UI).

## 4. Event payload format (Canvas Live Events alignment)

- **FR-EP6** Events SHALL use a Canvas Live Events–style envelope:
  ```jsonc
  {
    "metadata": {
      "event_name": "learning_outcome_result_created",
      "event_time": "2026-06-12T17:00:00Z",
      "producer": "mock-lms",
      "root_account_id": "…",
      "user_id": "…",
      "context_type": "Course",
      "context_id": "…",
      "event_id": "…",
      "correlation_id": "…",   // POC traceability extension (one per Action run)
      "action_id": "…"          // POC traceability extension (the Action that emitted it), when applicable
    },
    "body": { /* event-type-specific fields */ }
  }
  ```
- **FR-EP7** Bodies SHALL mirror the Canvas live-event body where one exists (`learning_outcome_result_created`, `course_completed`) and a documented POC shape for `badge_awarded`. The `course_completed` body SHALL include the learner's final course grade.
- **FR-EP8** Every emitted identifier the Context Builder depends on — whether carried in metadata or body fields — SHALL resolve against the [LMS Resource APIs](./mock-lms-apis.md) or the related account-user lookup path, so the Context Builder can dereference it (fail fast on emit if it can't).

## 5. Per-Action mapping (event → endpoints → id tracing)

For each Action, this documents the event payload, the LMS endpoints the Context Builder will read, and how it traces ids from event metadata/body to source data. (Endpoint paths: see [LMS APIs](./mock-lms-apis.md).)

| Action | Event | Relevant LMS endpoints | Context Builder id tracing |
|---|---|---|---|
| Submit skill mastery | `skill_mastered` | outcome by id; assignment by course/id; rubric lookup by `assignment.rubric_id` when needed; course modules; account users by UUID; assignment submission by course/assignment/user | `result_context_type=Course` + `result_context_id`→`course_id`, `associated_asset_type=Assignment` + `associated_asset_id`→`assignment_id`, `learning_outcome_id`→outcome, `root_account_id` + `user_uuid`→Canvas `user_id`, `assignment.rubric_id`→rubric, resolved Canvas `user_id` + `course_id` + `assignment_id`→submission |
| Submit final grade | `course_completed` | course; learner profile; enrollment (incl. `current_grade`/`current_points`); modules; pages; assignments; rubrics; learner submissions for the course | `body.course.id`→`course_id`, `metadata.user_id`→`user_id`, `user_id`→learner profile, `course_id`→course/modules/pages/assignments/rubrics, `course_id` + `user_id`→enrollment and learner submissions |
| Award badge (skill/course) | `badge_awarded` | badge by id (primary); user profile (optional) | `badge_id`→badge. Badge is pre-defined, so no learning-context endpoints are needed; `user_id`→profile is only for downstream account matching (the learner's email is also already in the badge). |

## 6. Repeatability

- **FR-EP9** Actions and their data SHALL be reproducible: the underlying data is a committed, seeded snapshot (see [LMS APIs §data model](./mock-lms-apis.md)), and Actions are re-runnable any number of times within a demo, each run producing fresh correlation/event ids over stable business keys.
- **FR-EP10** The UI SHALL let the operator **reset** emission state between runs (see [Demo UI](./mock-lms-ui.md)).

## 7. Where emission fits

Per the AWS architecture, flow is **Mock LMS → Amazon EventBridge → the internal orchestration runtime** (ADR-0011). The producer's emit is a `PutEvents` to EventBridge; it does not call downstream services directly. Locally, an in-process emitter stands in for the bus.

## 8. Out of scope

- `credential_eligible` events (§2).
- Mutating LMS data — an Action is a *trigger*, not a gradebook write (the seeded data is fixed).
- The downstream orchestration/LLM/policy/delivery.
