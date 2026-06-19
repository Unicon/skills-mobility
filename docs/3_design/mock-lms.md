# Mock LMS — Design

- Status: Draft
- Date: 2026-06-18

Related requirements: [Event Producer](../2_requirements/mock-lms-event-producer.md) · [LMS Resource APIs](../2_requirements/mock-lms-apis.md) · [Demo UI](../2_requirements/mock-lms-ui.md)
Design context: [**POC Component Boundary Matrix**](./poc-component-boundaries.md) — the source of truth for component names, ownership boundaries, and logical stores; this doc stays consistent with it. Aligns to the current working requirements in [Target POC Requirements](../2_requirements/target-poc-requirements.md) and the [Target POC Architecture](./architecture/target-poc-architecture.md).
Governing ADRs: [0002](../decisions/0002-frontend-architecture.md) · [0003](../decisions/0003-programming-language.md) · [0004](../decisions/0004-lif-usage.md) · [0007](../decisions/0007-llm-decision-service-decomposition.md) · [0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [0009](../decisions/0009-workflow-actions-orchestration-model.md) · [0011](../decisions/0011-orchestration-runtime-technology.md)

## 1. Overview

The **Mock LMS** is the POC's *source system* — it stands in for a real LMS (Open edX in production; modeled on **Canvas** for the POC). It has three pieces, kept distinct because they serve different purposes and evolve differently:

1. **Event Producer** — publishes credential events onto the bus.
2. **LMS Resource APIs** — Canvas-style read endpoints the Context Builder queries for decision context.
3. **Demo UI** — a course-centric console that **mimics an LMS** so a stakeholder can browse a course's materials and a learner's submissions, trigger grading, and then **compare that source data to the badge issued downstream** in the wallet — judging for themselves whether the AI orchestration did a good job.

> **Scope boundary (ADR-0002):** observing the orchestration itself — the live execution timeline, per-step status, LLM confidence/rationale, correlation tracing — is the job of the **Admin UI**, a *separate* application. This doc covers the Mock LMS only; the Admin UI is out of scope here. The Mock LMS makes the **source side** legible (course + submissions in, badge to compare against out); the Admin UI makes the **orchestration** legible.

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
          → Transformation Executor → Delivery Router → delivery (wallet)
```

(Component names — Orchestrator, Event Consumer, the specialized LLM Decision Services — follow the boundary matrix.) The Mock LMS is upstream of every orchestration decision. It does two things for the rest of the system: it **emits the events** that trigger workflows, and it **serves the source data** those workflows read.

### Design goals

- **Legible source side & repeatable** — a stakeholder can see the course materials and submissions that drove an event, and compare them to the issued badge; the same demo runs identically every time.
- **Drives the pipeline incrementally** — the Mock LMS can emit the full range of events the orchestration must handle (including ones that should *not* deliver), but we build it in phases: a happy-path end-to-end slice first with the decision services stubbed, then the events that exercise each LLM Decision Service. See §6 Phasing.
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

Three event types, in a Canvas Live Events–style `{ metadata, body }` envelope (full schema in [requirements §4](../2_requirements/mock-lms-event-producer.md)):

| Event | Modeled on | Body highlight |
|---|---|---|
| `skill_mastered` | Canvas `learning_outcome_result_created` | outcome id, score, mastery |
| `course_completed` | Canvas `course_completed` | final course grade |
| `badge_awarded` | POC-defined | badge id, acceptance status |

`metadata` adds `correlation_id` (one per Action run) and `action_id` for traceability. No `credential_eligible` (no realistic source event).

### Events that exercise the orchestration (happy + edge variants)

Each event type has a **happy variant** that should flow all the way to delivery, and an **edge variant** where the Workflow Actions planner should decide *not* to deliver. The happy variants drive the end-to-end pipeline and the Delivery Targets / Field Mapping / Field Synthesis / Transformation services; the edge variants make the Workflow Actions planner's non-delivery decisions testable (ADR-0009). **Both must be in the seed.**

| Event | Happy variant — delivers | Edge variant — planner declines to deliver | Primarily tests |
|---|---|---|---|
| `skill_mastered` | competency-level outcome | sub-competency (flat outcome, e.g. `1.2.3`) | happy → delivery + transformation services; edge → Workflow Actions "skip delivery" |
| `course_completed` | passing final grade | failing final grade | happy → delivery; edge → Workflow Actions early-terminate |
| `badge_awarded` | badge accepted, fetchable via GET badge by id | badge unaccepted (GET badge by id errors) | happy → delivery; edge → Workflow Actions acceptance-gate |

### Actions

The operator never emits raw events — a **Course contains Actions**, and each Action emits 1..N events for **one learner** or **all learners** (bulk → one event per enrolled learner). Action availability depends on course kind. See [requirements §3](../2_requirements/mock-lms-event-producer.md) for the Action catalog and the per-Action → endpoint → id-tracing mapping; the UI placement of these Actions is in §4.

### Emission control API

```
POST /demo/courses/{course_id}/actions   # run an Action (scope: one|all)
                                          # → returns the emitted envelope(s) + correlation_id synchronously
POST /demo/reset                          # reset emission state for a clean re-run
GET  /demo/courses                        # courses + the Actions each offers
```

One `correlation_id` per Action run, stamped into every emitted event. Emitting is a `PutEvents` to EventBridge (locally, an in-process emitter stands in). The trigger response returns the envelope(s) so the UI can show what was emitted; there is no live emission feed here — that lives in the Admin UI (§4).

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

The catalog is the **Mock LMS Resource / Event Data Store** (boundary matrix §7): read by the Event Producer, the LMS Resource APIs, and the Demo UI. It is assembled from two sources, then **captured → committed → replayed**:

- **Real roster base (PM-provided CSVs).** Canvas SIS-style exports — `course_sections.csv`, `users.csv`, `enrollments.csv` — provide realistic courses/sections, learners (with **real emails** and profile attributes), and enrollments (e.g. *Wasatch University*, *FINC-106 Introduction to Finance*). We import a **small demo subset** (a handful of courses + learners), not the full export (~143 sections / ~4k users / ~12k enrollments).
- **Generated academic + credential layer.** The CSVs don't include the activity/credential data our events need, so a **seeded generator** builds it on top of the imported roster, with **logically linked ids**: modules, outcomes (competency *and* sub-competency, e.g. flat `1.2.3`), module + final assignments, submissions with **passing and failing** grades, outcome results, rubrics, and badges (**accepted/fetchable and unaccepted**). It also tags each course a **kind** (standard vs digital-credential-supported).
- Together these guarantee **both course kinds** and **both variants of each event** (§2) are present.
- The assembled catalog is **captured to committed `fixtures/*.json`**; the runtime loads that frozen snapshot **read-only** and never re-runs the assembly. Deterministic — same inputs → byte-identical fixtures.
- Raw CSVs stay out of the repo (input artifacts); larger/bulk sets can live in gitignored `generated-fixtures/`, selectable via `MOCK_LMS_FIXTURES_DIR`.

This yields two repeatability guarantees: **source data** identical every run (deterministic APIs), and **emitted events** fresh-id'd per run over stable business keys.

---

## 4. Piece 3 — Demo UI

A **course-centric** console (`apps/mock-lms`) that mimics an LMS, so the demonstration makes sense to a stakeholder who knows what an LMS looks like. They browse a course and a learner's work, trigger a grading Action, and later compare that source data to the badge in the downstream wallet. See [requirements §2–3](../2_requirements/mock-lms-ui.md).

- **Inspect** — pick a course → browse its modules, outcomes, assignments, learners, submissions, rubrics (via the LMS Resource APIs — the same surface the Context Builder reads). This is the source data a viewer compares against the issued badge.
- **Trigger** — grading an assignment is the Action; the event it emits depends on the course kind and which assignment was graded (matrix below). Each Action runs for one learner or all learners.
- **Confirm** — after a trigger, the UI shows the emitted envelope(s) + correlation id returned synchronously, so the presenter can point to exactly what was emitted.

### Action matrix (what grading emits)

| Course kind | Grade a **module-level** assignment | Grade the **final** assignment |
|---|---|---|
| **Standard** | `skill_mastered` — outcome is a **sub-competency** or a **competency** | `course_completed` — **passing** or **failing** |
| **Digital-credential-supported** | `badge_awarded` for a **competency** — badge **accepted/fetchable** (GET badge by id) or **unaccepted** (errors) | `badge_awarded` for the **course** — accepted/fetchable or unaccepted |

The two variants in each cell are the happy/edge pair from §2; the seed carries both.

### Not in the Mock LMS UI (it's the Admin UI's job, ADR-0002)

The **live emission/execution timeline**, per-workflow execution detail, LLM confidence/rationale, and cross-system correlation tracing belong to the **Admin UI** — a separate SPA. The Mock LMS UI does not host a live feed; it shows source data + the synchronous emit confirmation. A presenter can copy a `correlation_id` from the confirmation to follow the same workflow in the Admin UI, but no shared navigation shell is required.

**Auth:** CloudFront-layer per ADR-0002 (decided — not Cognito), a **single demo user** with full capability (no instructor/admin split). Static SPA on S3 + CloudFront.

---

## 5. Cross-cutting design

### 5.1 Service shape (`services/mock-lms`)

- `api/resources/` — Canvas-style read routers (one per resource).
- `api/emit/` — Action execution (one/all learners), reset; returns the emitted envelope(s) synchronously.
- `catalog/` — entity models, in-memory read-only store, fixture loader.
- `generators/` — seeded Faker generator (authoring tool; not in the runtime path).
- `events/` — envelope + body builders, id/correlation generation (imports `libs/events`).
- `emitter/` — `LocalEmitter` (dev) / `EventBridgeEmitter` (AWS).

(No SSE/emission-log module — the persistent, cross-system emission view is the Admin UI's, reading the Orchestrator's execution log per the boundary matrix §6.)

### 5.2 Local vs AWS

The bus is behind an `Emitter` interface: `LocalEmitter` captures envelopes in-process (dev/tests, no AWS); `EventBridgeEmitter` does `PutEvents` and deploys as the FastAPI service on Lambda. The same abstraction lets tests assert on emitted envelopes without a bus. (Infra via CDK — not yet built.)

### 5.3 Audit & traceability

Every emission carries `correlation_id` + `action_id` + a unique `event_id`, propagated to the bus, so the Orchestrator's execution log (ADR-0011 / boundary matrix §6) — surfaced in the Admin UI — ties back to the exact Action a presenter triggered.

---

## 6. Phasing — MVP happy path first

We will **not** stand up all the LLM Decision Services before anything runs end-to-end. The first milestone is a working pipe; the AI decisioning is layered in afterward.

**Phase 1 — end-to-end happy path, middle stubbed.** Drive one happy event (e.g. competency mastery / passing grade / accepted badge) from the Mock LMS through to a delivered badge, **bypassing** the Workflow Actions, Delivery Targets, Field Mapping, Field Synthesis, and Transformation services. The slice runs as:

1. The **Context Builder** deterministically fetches the source data for the event from the LMS Resource APIs (its real job — unchanged in Phase 1).
2. The **Orchestrator** fills the **required OBv3 fields with placeholder data** and sends that record to the **Delivery Router**. (The offloaded LLM Decision Service jobs are stubbed *in the Orchestrator* so they all sit in one place, rather than in the Context Builder.)
3. The **Delivery Router** invokes the **LearnCard Issuer Adapter**, which issues the credential and returns the signed record to the Orchestrator.
4. The **Orchestrator** skips the Decision Services and stubs whatever updates the issued OBv3 record needs to be valid input for the wallet, then sends it back to the **Delivery Router**.
5. The **Delivery Router** invokes the **LearnCard Wallet Adapter**, delivering the badge to the LearnCloud wallet.

Goal: prove the end-to-end pipe and the demo comparison (source data ↔ wallet badge) before any LLM decisioning exists.

**Phase 2+ — replace the stubs.** Incrementally swap the stubbed middle for the real LLM Decision Services and the two-loop transformation pipeline, and add the **edge-variant** events (sub-competency, failing grade, unaccepted badge) so the Workflow Actions planner's non-delivery branches and the other services become testable.

From the Mock LMS's perspective: Phase 1 needs only the **happy** event variants plus the LMS Resource APIs the Context Builder reads; the edge variants and the full event matrix (§2) come online with Phase 2. Detailed, step-by-step **happy-path test procedures** will live under `4_operations/` once we build them; this section captures the phasing intent so the build is sequenced correctly.

---

## 7. Build order

1. `libs/events`: envelope + 3 event-type schemas.
2. `services/mock-lms`: catalog + generator + LMS Resource APIs + `LocalEmitter` + emission API (Actions), returning the envelope synchronously.
3. Assemble catalog: import a demo subset of the roster CSVs (courses/learners/enrollments) + generate the academic/credential layer — both course kinds + **both variants of each event** (happy: competency mastery / passing / accepted-fetchable badge; edge: sub-competency / failing / unaccepted badge).
4. `apps/mock-lms`: course view → inspect (modules/submissions) → Action triggers → emitted-envelope confirmation.
5. Phase 1 end-to-end happy path with the middle stubbed (§6). This spans the downstream components the slice needs, in order:
   1. **Event Consumer** — ingress + idempotency, starts a workflow run.
   2. **Orchestrator** — runs the slice; fills the required OBv3 fields with placeholder data and stubs the wallet-input updates (the offloaded Decision Service jobs).
   3. **Context Builder** — deterministic source-data fetch from the LMS Resource APIs.
   4. **Delivery Router — LearnCard Issuer Adapter** — issues the credential and returns it to the Orchestrator.
   5. **Delivery Router — LearnCard Wallet Adapter** — delivers the badge to the wallet.
6. `EventBridgeEmitter` + CDK infra; deploy.
7. CloudFront-layer auth (ADR-0002).

## 8. Open questions

- **Account provisioning for delivery:** the downstream wallet may require the mock learner to already have an account before a badge can be delivered. The roster CSVs give us concrete learner emails, so we'd fix a handful of those as the demo learners and pre-create their wallet accounts. To be confirmed when we wire delivery.
- **Where the happy-path test lives:** this doc captures the phasing; the detailed end-to-end test steps will be a `4_operations/` doc when Phase 1 is built.
- **Sub-competency representation:** how exactly to encode the parent/sub-competency outcome hierarchy in flat Canvas outcomes so the Workflow Actions LLM can infer structure (naming convention vs. an explicit field).
- **Rubric fidelity:** how much rubric detail the transformation pipeline actually needs in a badge before we over-model the rubric endpoint.

## 9. References

- [POC Component Boundary Matrix](./poc-component-boundaries.md) — component names, ownership boundaries, stores
- [Target POC Requirements](../2_requirements/target-poc-requirements.md) · [Target POC Architecture](./architecture/target-poc-architecture.md) — current working system-level requirements & architecture this design aligns to
- [ADR-0012 MCP Client Layer Deferred](../decisions/0012-mcp-client-layer-deferred.md)
- Requirements: [Event Producer](../2_requirements/mock-lms-event-producer.md), [LMS Resource APIs](../2_requirements/mock-lms-apis.md), [Demo UI](../2_requirements/mock-lms-ui.md)
- [ADR-0002 Frontend Architecture](../decisions/0002-frontend-architecture.md)
- [ADR-0003 Programming Language](../decisions/0003-programming-language.md)
- [ADR-0004 LIF Component Usage](../decisions/0004-lif-usage.md)
- [ADR-0007 LLM Decision Service Decomposition](../decisions/0007-llm-decision-service-decomposition.md)
- [ADR-0008 Transformation Mapping Service Decomposition](../decisions/0008-transformation-mapping-service-decomposition.md)
- [ADR-0009 Workflow Actions Orchestration Model](../decisions/0009-workflow-actions-orchestration-model.md)
- [ADR-0011 Orchestration Runtime Technology](../decisions/0011-orchestration-runtime-technology.md)
