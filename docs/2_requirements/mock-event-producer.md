# Mock Event Producer — Requirements

Status: Draft
Date: 2026-06-10
Owner: (mock event producer task)
Related: [POC Requirements](./poc-requirements.md) · [Design](../3_design/mock-event-producer.md) · [ADR-0001 Repo Structure](../decisions/0001-repo-structure.md) · [ADR-0002 Frontend Architecture](../decisions/0002-frontend-architecture.md) · [ADR-0003 Programming Language](../decisions/0003-programming-language.md)

## 1. Purpose

The Mock Event Producer is the **source system** for the Skills Mobility Infrastructure POC. It stands in for a real LMS (Open edX in production; modeled on **Canvas LMS** for the POC) and does two jobs:

1. **Emits credential-relevant events** (skill mastered, course completed, badge awarded, credential eligible) into the orchestration pipeline.
2. **Serves Canvas-style read APIs** ("LMS Metadata APIs") that the Context Builder calls to assemble decision context (course, enrollment, assignments, outcomes, submissions, etc.).

It also provides a **demo-facing UI** (the "Mock LMS" app from ADR-0002) that lets an instructor/administrator inspect the mock data and trigger a **repeatable** set of events on demand, with a **real-time log and visualization** of what was emitted.

The producer is the thing a presenter drives during a sales demo. Its job is to make the downstream AI orchestration *legible and repeatable*: a viewer should be able to look at the source data (a graded assignment, an outcome result), trigger an event, and then compare it against the badge the system issues downstream.

## 2. Scope

### In scope

- A mock LMS backend service exposing **Canvas-style metadata REST APIs** (read-only) over a fixed, seeded data set.
- An **event emission control API** that publishes structured events to the POC event bus (Amazon EventBridge per the AWS architecture).
- **Canvas Live Events–shaped event payloads** for the supported event types.
- A set of **canonical, repeatable demo scenarios** (seed data + scripted event sequences) checked into the repo.
- A **React SPA** (`apps/mock-lms`) that lets a signed-in instructor/admin browse the mock data, trigger single events or full scenarios, and watch an emission log/timeline update in real time.
- **Correlation identifiers** stamped on every emitted event for end-to-end traceability.
- Authentication for the UI, aligned with ADR-0002 (see §7).

### Out of scope

Consistent with the parent POC's out-of-scope list, and additionally:

- Real Canvas API parity or completeness — only the endpoints in §5.3 are mocked, only with the fields the Context Builder consumes.
- Writes/mutations to mock data through the Canvas-style APIs (the data set is fixed/seeded; "grading" in the UI triggers an *event*, it does not durably mutate an LMS gradebook — see §6.2).
- The downstream orchestration, LLM, policy, delivery, and Admin-app workflow visualization (those are separate components; ADR-0002's Admin app owns the *cross-system* workflow view — this component only visualizes *its own emissions*).
- Production-grade auth, multi-tenant concerns, real Open edX eventing.

## 3. Definitions

- **Event Producer** — the backend capability that publishes events to the bus.
- **LMS Metadata APIs** — the Canvas-style read endpoints the Context Builder queries (§5.3).
- **Scenario** — a named, versioned bundle of seed data + an ordered sequence of events that reproduces a known demo narrative (e.g. "Ada masters the Data Analysis outcome").
- **Emission** — a single act of publishing one event to the bus, with a correlation id.
- **Live Event envelope** — the Canvas-style `{ metadata, body }` wrapper for an emitted event (§5.2).

## 4. Actors

| Actor | Description | Primary needs |
|---|---|---|
| **Instructor** | Demo persona who "teaches" a course | Browse their course(s), assignments, students, outcomes; grade/complete an item to trigger an event |
| **Administrator** | Demo operator/presenter | Browse all mock data; pick and run scenarios; replay; inspect raw payloads; watch the live emission log |
| **Context Builder** (system) | Downstream service | Read mock LMS metadata via the Canvas-style APIs |
| **Event Consumer** (system) | Downstream service | Receive emitted events from the bus |

Per ADR-0002, POC users **log in directly as** the instructor or administrator role for the app they are using. Persona masquerading is deferred (see §7).

## 5. Functional Requirements

### 5.1 Event emission

- **FR-E1** The producer SHALL publish structured JSON events to the POC event bus (EventBridge).
- **FR-E2** The producer SHALL support these event types for the POC happy paths:
  - `skill_mastered` (modeled on Canvas `learning_outcome_result_created`)
  - `course_completed` (modeled on Canvas `course_completed`)
  - `badge_awarded`
  - `credential_eligible`
- **FR-E3** Each emitted event SHALL carry a **correlation id** (and a scenario id when emitted as part of a scenario) so downstream execution can be traced back to the triggering action.
- **FR-E4** Emission SHALL be **idempotency-friendly**: each emission carries a unique event id, and re-running a scenario produces fresh ids while preserving stable business keys (learner, course, outcome) so the demo is repeatable without colliding with prior runs.
- **FR-E5** The producer SHALL support emitting a **single event** or an **ordered sequence** (a scenario) with optional inter-event delays.
- **FR-E6** The producer SHALL return, synchronously to the caller (UI), the emitted envelope(s) and correlation id(s) so the UI can display and link them.

### 5.2 Event payload format (Canvas Live Events alignment)

- **FR-P1** Events SHALL use a Canvas Live Events–style envelope:
  ```jsonc
  {
    "metadata": {
      "event_name": "learning_outcome_result_created",
      "event_time": "2026-06-10T17:00:00Z",
      "producer": "mock-lms",
      "root_account_uuid": "…",
      "user_id": "…",
      "context_type": "Course",
      "context_id": "…",
      "correlation_id": "…",   // POC traceability extension
      "scenario_id": "…"       // POC traceability extension, when applicable
    },
    "body": { /* event-type-specific fields */ }
  }
  ```
- **FR-P2** Event bodies SHALL mirror the relevant Canvas live-event body shape where one exists (`learning_outcome_result_created`, `course_completed`), and a documented POC-defined shape where one does not (`badge_awarded`, `credential_eligible`).
- **FR-P3** Identifiers used in event bodies (course id, user id, outcome id, assignment id) SHALL match the ids served by the LMS Metadata APIs (§5.3), so the Context Builder can resolve them.

### 5.3 LMS Metadata APIs (Canvas-style read endpoints)

The producer SHALL expose the following read endpoints. Paths and query shapes mirror Canvas so the integration is realistic; only fields consumed by the Context Builder need be populated.

| Purpose | Canvas-style endpoint |
|---|---|
| Get course | `GET /api/v1/courses/{course_id}` |
| Get learner enrollment | `GET /api/v1/courses/{course_id}/enrollments?user_id={user_id}` |
| Get course modules / static structure | `GET /api/v1/courses/{course_id}/modules?include[]=items` |
| Get pages / static content | `GET /api/v1/courses/{course_id}/pages` and `GET /api/v1/courses/{course_id}/pages/{url}` |
| Get assignments | `GET /api/v1/courses/{course_id}/assignments` |
| Get outcome (skill) details | `GET /api/v1/outcomes/{outcome_id}` |
| Get outcome results | `GET /api/v1/courses/{course_id}/outcome_results?user_ids[]={user_id}&outcome_ids[]={outcome_id}&include[]=alignments` |
| Get outcome-aligned assignments | `GET /api/v1/courses/{course_id}/outcome_alignments?student_id={user_id}` |
| Get learner submissions | `GET /api/v1/courses/{course_id}/students/submissions?student_ids[]={user_id}&assignment_ids[]={assignment_id}` |

- **FR-A1** Endpoints SHALL be read-only and serve from the seeded scenario data set.
- **FR-A2** Responses SHALL be stable and deterministic for a given scenario (same request → same response), so demos are reproducible.
- **FR-A3** The producer SHALL also expose **business-friendly lookups** used in the happy-path sketches: get badge by id, get skill (outcome) by id, get course by id, get course assignments with skill id, get course submissions by assignment id and user id. These MAY be thin views over the Canvas-style endpoints above.
- **FR-A4** Unknown ids SHALL return Canvas-style `404` shapes; the API SHALL not 500 on missing optional includes.

### 5.4 Scenarios & repeatability

- **FR-S1** Scenarios SHALL be defined as **declarative, version-controlled fixtures** (seed data + event script), not hard-coded.
- **FR-S2** The POC SHALL ship at least the three canonical happy paths from the whiteboard: **Skill Mastered**, **Course Completed**, **Badge Awarded**.
- **FR-S3** A scenario SHALL be **re-runnable** any number of times within a demo, each run producing a fresh correlation/event id set.
- **FR-S4** The UI SHALL let the operator **reset** to a clean scenario state between runs.

### 5.5 Demo UI (`apps/mock-lms`)

- **FR-U1** The UI SHALL require sign-in (see §7) and present an instructor or administrator experience.
- **FR-U2** **Inspect:** The UI SHALL let the user browse the mock data backing a scenario — course, modules, assignments, students, outcomes, outcome results, and submissions — sourced from the LMS Metadata APIs (so the UI exercises the same endpoints the Context Builder uses).
- **FR-U3** **Trigger:** The UI SHALL provide controls to emit a single event (e.g. an instructor "grades the last assignment" → emits `learning_outcome_result_created`) or run a full scenario.
- **FR-U4** **Inspect payloads:** The UI SHALL display the exact emitted envelope (raw JSON) for any emission.
- **FR-U5** **Real-time log:** The UI SHALL show a live, append-as-it-happens log/timeline of emissions, including event type, timestamp, correlation id, and target.
- **FR-U6** **Visualization:** The UI SHALL present a simple visual representation of the emission stream suitable for presenting to an audience (e.g. a timeline or flow strip), with the most recent event highlighted.
- **FR-U7** The UI SHALL surface correlation ids in a copyable form so a presenter can pivot to the Admin app to follow the same workflow downstream.

## 6. Behavioral notes

### 6.1 Where emission fits the architecture

Per the AWS architecture diagram, flow is: **Mock Event Producer → Amazon EventBridge → Event Consumer (Lambda) → Step Functions**. The producer's "emit" action is a `PutEvents` to EventBridge; the producer does not call downstream services directly.

### 6.2 "Grading" is a trigger, not a mutation

An instructor action in the UI (grade/complete) is a **demo trigger** that emits the corresponding event. For the POC the underlying scenario data is fixed; the action does not durably rewrite a gradebook. (If a later demo needs the inspected data to reflect the action, that becomes a follow-up requirement — see §9.)

## 7. Authentication

Per ADR-0002, the POC uses **frontend auth at the CloudFront layer (not Cognito)**, with users logging in **directly as** the instructor/admin role for the app they are using; persona masquerading is deferred.

- **NFR-AUTH:** The UI SHALL authenticate at the CloudFront layer and the service SHALL trust an injected role claim (instructor/admin). No Cognito user pool is introduced for the POC.
- The "become an instructor/administrator" need from the soft requirements is satisfied by **direct role login** (ADR-0002), not by login-then-masquerade. A Cognito-backed identity flow with role switching remains a possible future evolution, but only via a follow-up ADR (or amendment to ADR-0002) — it is explicitly not part of this component's scope.

The design isolates auth behind a single role-resolution dependency (design §7) so that a future issuer change would not touch handlers, but the POC implementation is CloudFront-layer auth.

## 8. Non-functional requirements

- **NFR-1 (Repeatable):** Identical scenario runs are reproducible and demo-safe (§5.4).
- **NFR-2 (Legible):** Every emission is inspectable as raw JSON and tied to a correlation id (§5.5).
- **NFR-3 (Lightweight):** Aligns with the ADRs' "keep the POC lightweight" intent — Python/FastAPI backend (ADR-0003), React SPA on S3+CloudFront (ADR-0002).
- **NFR-4 (Low-latency UI feedback):** The real-time log SHOULD reflect an emission within ~1s of the trigger for a credible live demo.
- **NFR-5 (Deterministic APIs):** Metadata API responses are stable per scenario (§5.3).
- **NFR-6 (Traceable):** Correlation ids propagate from UI trigger → emitted event → bus, enabling the Admin app to continue the trace.

## 9. Assumptions & dependencies

- Depends on an EventBridge bus (or local stand-in) provisioned by `infra/` (ADR-0001).
- Depends on the agreed event-name vocabulary and body shapes being shared with the Event Consumer / Context Builder (a contract; ADR-0001 flags Python⇄TS contract ownership as a deferred decision — for this component the producer is the source of truth for event/payload schemas).
- Assumes the Context Builder consumes the Canvas-style endpoints in §5.3; if it needs additional fields/endpoints, this list grows.
- Local development uses a local event bus / queue stand-in and seeded fixtures; no real Canvas instance is required.

## 10. Success criteria

- A presenter can sign in, pick the "Skill Mastered" scenario, inspect the course/outcome/submission data, click one control, and see the `learning_outcome_result_created` event appear in the live log with a correlation id — and re-run it cleanly.
- The Context Builder can resolve every id in an emitted event against the LMS Metadata APIs.
- All three canonical happy paths (Skill Mastered, Course Completed, Badge Awarded) emit valid, downstream-consumable events.

## 11. Open questions

1. Real-time transport for the live log: WebSocket (API Gateway) vs SSE vs optimistic client-side append? (see design doc; SSE recommended)
2. Does the sales demo need the inspected mock data to *change* after a trigger (§6.2), or is trigger-only sufficient?
3. Is `credential_eligible` emitted directly by the producer, or derived downstream from `skill_mastered`/`course_completed`? (Affects which event types the producer owns.)
4. Should scenarios be authored in-repo only, or editable from the Admin UI?
