# Mock LMS — Design

- Status: Draft
- Date: 2026-06-17

Related requirements: [Event Producer](../2_requirements/mock-lms-event-producer.md) · [LMS Resource APIs](../2_requirements/mock-lms-apis.md) · [Demo UI](../2_requirements/mock-lms-ui.md)
Design context: **POC Component Boundary Matrix** (`poc-component-boundaries.md`, PR #10 — pending merge) — the source of truth for component names, ownership boundaries, and logical stores; this doc stays consistent with it.
Governing ADRs: [0002](../decisions/0002-frontend-architecture.md) · [0003](../decisions/0003-programming-language.md) · [0004](../decisions/0004-lif-usage.md) · [0007](../decisions/0007-llm-decision-service-decomposition.md) · [0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [0009](../decisions/0009-workflow-actions-orchestration-model.md) · ADR-0011 (PR #9, pending merge)

## 1. Overview

The **Mock LMS** is the POC's *source system* — it stands in for a real LMS (Open edX in production; modeled on **Canvas** for the POC). It has three pieces, kept distinct because they serve different purposes and evolve differently:

1. **Event Producer** — publishes credential events onto the bus.
2. **LMS Resource APIs** — Canvas-style read endpoints the Context Builder queries for decision context.
3. **Demo UI** — a course-centric console that makes the downstream orchestration legible and repeatable for a stakeholder demo.

Its job is to drive and make legible the rest of the system: a presenter triggers an Action, an event flows through the Orchestrator, and the issued credential can be compared side-by-side with the source data the Mock LMS served.

### Where it sits in the architecture

```
┌─ Mock LMS ─────────────────────────────────────────┐
│  Demo UI ──reads──► LMS Resource APIs ◄──reads──────┼─── Context Builder (downstream)
│     │                      ▲                         │
│     └─triggers Action─► Event Producer               │
└──────────────────────────────┬──────────────────────┘
                                │ PutEvents
                                ▼
                         Amazon EventBridge
                                │
                                ▼
              Event Consumer  (ingress; primary idempotency)
                                │
                                ▼
        Orchestrator  (project-internal runtime, ADR-0011)
          → Workflow Actions plan (ADR-0009)
          → Delivery Targets · Field Mapping · Field Synthesis (ADR-0007/0008)
          → Transformation Executor → Delivery Router → delivery
```

(Component names — Orchestrator, Event Consumer, the specialized LLM Decision Services — follow the boundary matrix.) The Mock LMS is upstream of every orchestration decision. It does two things for the rest of the system: it **emits the events** that trigger workflows, and it **serves the source data** those workflows read. Designing it well means (a) being able to emit the *range* of events the orchestration must handle — including the ones that should *not* result in delivery — and (b) serving the data the transformation pipeline needs to build a credential.

### Design goals

- **Legible & repeatable** — a viewer can follow source data → event → issued credential; the same demo runs identically every time.
- **Feeds the real pipeline** — the data and events exercise the actual orchestration/transformation paths defined in ADRs 0007–0009 and 0011, not a happy-path-only subset.
- **Lightweight** — Python/FastAPI service + React SPA (ADR-0002/0003), seeded fixtures, no real Canvas or AWS required for local dev.

### Boundaries & repo placement (ADR-0001)

The boundary matrix treats **Event Producer** and **LMS Resource APIs** as two distinct boundaries. For the POC they are **co-deployed in one FastAPI service** (`services/mock-lms/`) as separate routers/modules — kept cleanly separable so they can split into independent deployables later without rework.

| Boundary / piece | Path | Tech |
|---|---|---|
| Event Producer | `services/mock-lms/` (emit + events modules) | Python 3.12 + FastAPI + Pydantic |
| LMS Resource APIs | `services/mock-lms/` (resources module) | Python 3.12 + FastAPI + Pydantic |
| Demo UI | `apps/mock-lms/` | React + TypeScript + Vite |
| Event contracts | `libs/events/` | Pydantic (TS types generated into `packages/` if needed) |

---

## 2. Piece 1 — Event Producer

### Events

Three event types (the POC happy paths), in a Canvas Live Events–style `{ metadata, body }` envelope (full schema in [requirements §4](../2_requirements/mock-lms-event-producer.md)):

| Event | Modeled on | Body highlight |
|---|---|---|
| `skill_mastered` | Canvas `learning_outcome_result_created` | outcome id, score, mastery |
| `course_completed` | Canvas `course_completed` | final course grade |
| `badge_awarded` | POC-defined | badge id, acceptance status |

`metadata` adds `correlation_id` (one per Action run) and `action_id` for traceability. No `credential_eligible` (no realistic source event).

### Actions

The operator never emits raw events — a **Course contains Actions**, and each Action emits 1..N events for **one learner** or **all learners** (bulk → one event per enrolled learner). Action availability depends on course kind (standard vs digital-credential-supported). See [requirements §3](../2_requirements/mock-lms-event-producer.md) for the Action catalog and the per-Action → endpoint → id-tracing mapping.

### Exercising the orchestration paths (the design-critical part)

ADR-0009 chose hierarchical planning specifically so the Workflow Actions LLM can decide *not* to deliver. For that to be demonstrable, the Mock LMS must be able to emit events that drive those branches. The seed data and Actions are designed to produce each:

| Orchestration use case (ADR-0009) | What the Mock LMS must emit | Seed data required |
|---|---|---|
| Sub-competency mastery that shouldn't issue a badge | `skill_mastered` for a **hierarchically-named flat outcome** (e.g. `1.2.3`) | outcomes at both parent and sub-competency levels |
| Failing-grade completion → no delivery | `course_completed` with a **failing** final grade | a learner whose enrollment carries a failing `current_grade` |
| Badge not yet accepted → abort delivery | `badge_awarded` where the badge is **unaccepted** | a badge in an `unaccepted` state retrievable via GET badge by id |

This is the main way the Mock LMS earns its keep as more than a happy-path emitter — it lets the demo show the LLM planner correctly terminating early.

### Emission control API

```
POST /demo/courses/{course_id}/actions   # run an Action (scope: one|all)
POST /demo/reset                          # clear emission state for a clean re-run
GET  /demo/courses                        # courses + the Actions each offers
GET  /demo/emissions?since=<cursor>       # backfill for the UI
GET  /demo/stream                         # SSE live feed (§5.2)
```

One `correlation_id` per Action run, stamped into every emitted event. Emitting is a `PutEvents` to EventBridge (locally, an in-process emitter stands in).

**Idempotency boundary (per the matrix §4):** the Event Producer is only **idempotency-*friendly*** — it emits stable business ids plus fresh `event_id`/`correlation_id` each run. Deduplicating redelivered events is the downstream **Event Consumer's** job (the ingress idempotency boundary), not the producer's.

---

## 3. Piece 2 — LMS Resource APIs

Canvas-style read endpoints (route group/tag `resources`). Full table in [requirements §2](../2_requirements/mock-lms-apis.md): course, enrollment (with `current_grade`/`current_points`), modules, pages, assignments, outcomes, outcome_results (+alignments), submissions, **user profile** (email as badge recipient id), **rubrics**, and a POC-defined **GET badge by id**.

### What these feed (ADR-0007 / 0008)

The Context Builder reads these to assemble decision context; the transformation pipeline (ADR-0008) consumes them across its two loops:

| Pipeline stage (ADR-0008) | Mock LMS data it reads |
|---|---|
| Loop 1 — credential template (course-level) | course, modules, pages, assignments, outcome/skill, **rubrics** |
| Loop 2 — learner record (learner-level) | submissions, outcome_results, enrollment, **user profile** |

> Note: the **skills-framework context** (O*NET, etc.) that ADR-0008's Loop 1 also needs is *not* supplied by the Mock LMS — it's an external context source. The Mock LMS provides only the LMS-side learning context.

This is why the endpoint set grew beyond the original sketch: rubrics and course content are the inputs people actually want inside a badge, and the profile email is the badge recipient identity.

**Fetch ownership (per the matrix §5):** *which* of these endpoints to call for a given event is decided deterministically by the **Context Builder** (via versioned fetch profiles keyed by event type) — the Mock LMS only serves the data. The per-Action → endpoint table in the requirements documents those relationships; it does not place fetch logic in the Mock LMS.

### Data model & repeatability

The catalog is the **Mock LMS Resource / Event Data Store** (boundary matrix §7): written by the seed-capture process, read by the Event Producer, the LMS Resource APIs, and the Demo UI. Mock data follows **generate → capture → commit → replay**:

- A **seeded generator** builds the catalog with **logically linked ids** (course → modules → outcomes → aligned assignments → submissions → results all cross-reference), so a viewer can follow the chain, and a guaranteed primary happy path.
- Its output is **captured to committed `fixtures/*.json`**; the runtime loads that frozen snapshot **read-only** and never runs the generator. Same seed → byte-identical data.
- The seed includes **both course kinds** and the variants needed for the orchestration use cases above (a failing learner, a sub-competency outcome, an unaccepted badge).
- `generated-fixtures/` (gitignored) holds larger experimental sets, selectable via `MOCK_LMS_FIXTURES_DIR`.

This yields two repeatability guarantees: **source data** identical every run (deterministic APIs), and **emitted events** fresh-id'd per run over stable business keys.

---

## 4. Piece 3 — Demo UI

A **course-centric** console (`apps/mock-lms`) — it presents a course as it would appear in a real LMS, so viewers understand the tool hooks into their LMS rather than firing abstract events. See [requirements §2–3](../2_requirements/mock-lms-ui.md).

- **Inspect** — pick a course → browse its modules, outcomes, assignments, learners, submissions, rubrics (via the LMS Resource APIs — the same surface the Context Builder reads).
- **Trigger** — Action buttons placed in context: *submit skill mastery* at the relevant module; *submit final grade* / *award badge* at the course level. Each runs for one learner or all learners. The Action set depends on the course kind.
- **Observe** — a live SSE timeline of emissions (type, time, correlation id, target), raw-envelope view, copyable correlation ids, and replay/reset.

The Demo UI is a **separate SPA from the Admin UI** (boundary matrix §3 / ADR-0002) — they share no navigation shell. The copyable correlation id is the optional contextual hop a presenter uses to follow the same workflow into the Admin UI; nothing more is required between them.

**Auth:** CloudFront-layer per ADR-0002 (decided — not Cognito), a **single demo user** with full capability (no instructor/admin split). Static SPA on S3 + CloudFront.

---

## 5. Cross-cutting design

### 5.1 Service shape (`services/mock-lms`)

- `api/resources/` — Canvas-style read routers (one per resource).
- `api/emit/` — Action execution (one/all learners), reset.
- `api/stream/` — SSE feed.
- `catalog/` — entity models, in-memory read-only store, fixture loader.
- `generators/` — seeded Faker generator (authoring tool; not in the runtime path).
- `events/` — envelope + body builders, id/correlation generation (imports `libs/events`).
- `emitter/` — `LocalEmitter` (dev) / `EventBridgeEmitter` (AWS).
- `emissionlog/` — bounded ring buffer + read/stream.

### 5.2 Real-time feed

Server-Sent Events (`GET /demo/stream`) — the lightest transport that gives a genuine real-time, multi-viewer stream (presenter + audience screens) and composes with static S3+CloudFront hosting. The handler tails the in-memory emission log by cursor; `GET /demo/emissions?since=` provides backfill. The triggering client may optimistically echo and reconcile by `emission_id`.

### 5.3 Local vs AWS

The bus is behind an `Emitter` interface: `LocalEmitter` captures envelopes in-process (dev/tests, no AWS); `EventBridgeEmitter` does `PutEvents` and deploys as the FastAPI service on Lambda. The same abstraction lets tests assert on emitted envelopes without a bus. (Infra via CDK — not yet built.)

### 5.4 Audit & traceability

Every emission carries `correlation_id` + `action_id` + a unique `event_id`, propagated to the bus, so the Orchestrator's execution log (ADR-0011 / boundary matrix §6) ties back to the exact Action a presenter triggered.

---

## 6. Build order

1. `libs/events`: envelope + 3 event-type schemas.
2. `services/mock-lms`: catalog + generator + LMS Resource APIs + `LocalEmitter` + emission API (Actions).
3. Seed catalog: both course kinds + the orchestration use-case variants (failing grade, sub-competency outcome, unaccepted badge).
4. SSE feed + emission log.
5. `apps/mock-lms`: course view → Action triggers → live timeline.
6. `EventBridgeEmitter` + CDK infra; deploy.
7. CloudFront-layer auth (ADR-0002).

## 7. Open questions

- **Account provisioning for delivery:** the downstream wallet may require the mock learner to already have an account before a badge can be delivered. We may need to fix a handful of test learner emails as constants and pre-create wallet accounts. To be confirmed when we wire delivery.
- **Bulk inspection:** if we manually validate bulk (all-learner) Action outputs, the UI may need to show per-learner input data for a bulk run — deferred until we know whether bulk runs get manual validation.
- **Sub-competency representation:** how exactly to encode the parent/sub-competency outcome hierarchy in flat Canvas outcomes so the Workflow Actions LLM can infer structure (naming convention vs. an explicit field).
- **Rubric fidelity:** how much rubric detail the transformation pipeline actually needs in a badge before we over-model the rubric endpoint.

## 8. References

- **POC Component Boundary Matrix** (`poc-component-boundaries.md`, PR #10 — pending merge) — component names, ownership boundaries, stores
- Requirements: [Event Producer](../2_requirements/mock-lms-event-producer.md), [LMS Resource APIs](../2_requirements/mock-lms-apis.md), [Demo UI](../2_requirements/mock-lms-ui.md)
- [ADR-0002 Frontend Architecture](../decisions/0002-frontend-architecture.md)
- [ADR-0003 Programming Language](../decisions/0003-programming-language.md)
- [ADR-0004 LIF Component Usage](../decisions/0004-lif-usage.md)
- [ADR-0007 LLM Decision Service Decomposition](../decisions/0007-llm-decision-service-decomposition.md)
- [ADR-0008 Transformation Mapping Service Decomposition](../decisions/0008-transformation-mapping-service-decomposition.md)
- [ADR-0009 Workflow Actions Orchestration Model](../decisions/0009-workflow-actions-orchestration-model.md)
- ADR-0011 Orchestration Runtime Technology — *PR #9, pending merge*
