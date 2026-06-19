# Mock LMS — Design

Status: Draft
Date: 2026-06-12
Related: [Requirements: Event Producer](../2_requirements/mock-lms-event-producer.md) · [APIs](../2_requirements/mock-lms-apis.md) · [UI](../2_requirements/mock-lms-ui.md) · [ADR-0001](../decisions/0001-repo-structure.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0003](../decisions/0003-programming-language.md)

## 1. Overview

The **Mock LMS** is three parts across the ADR-0001 monorepo:

| Part | Path | Tech (ADR-0003) | Role |
|---|---|---|---|
| Service | `services/mock-lms/` | Python 3.12 + FastAPI + Pydantic | LMS Resource APIs + emission control API + SSE feed |
| Demo UI | `apps/mock-lms/` | React + TypeScript SPA | Course-centric inspect, trigger Actions, live emission feed |
| Event contracts | `libs/events/` (Py) + optionally `packages/event-contracts/` (TS) | Pydantic / generated TS | Event names, envelope, body schemas — the producer is source of truth |

The **Event Producer** is the only component that writes to the bus. The **UI** reads data from the LMS Resource APIs and triggers Actions that emit the related events; it never writes to the bus itself. The Context Builder (downstream) reads the LMS Resource APIs directly.

```
┌──────────────── apps/mock-lms (React SPA, S3+CloudFront) ────────────────┐
│  Course view → modules → Action buttons   Live emission feed (SSE)         │
└──────────────┬───────────────────────────────┬──────────────▲────────────┘
               │ GET LMS Resource APIs           │ POST actions  │ SSE
               ▼                                 ▼               │
┌──────────────────────── services/mock-lms (FastAPI) ──────────┴──────────┐
│  LMS Resource APIs ──reads──► Mock LMS catalog (seeded, read-only)         │
│  Emission API (Actions) ──build envelope──► Emitter ──PutEvents──► EventBridge
│  Emission API ──record──► Emission Log (ring) ──► SSE feed                 │
└────────────────────────────────────────┬─────────────────────────────────┘
                                          ▼
                          EventBridge → internal orchestration runtime (ADR-0011, downstream)
```

## 2. Service modules

- `api/resources/` — Canvas-style read routers (one per resource: courses, enrollments, modules, pages, assignments, outcomes, submissions, **account users**, **users/profile**, **rubrics**, **badges**).
- `api/emit/` — emission control: take an Action, run it (one or all learners), reset.
- `api/stream/` — SSE endpoint for the live feed.
- `catalog/` — the Mock LMS catalog: data models, in-memory store, fixture loader.
- `generators/` — seeded Faker generator (authoring tool; see §7).
- `events/` — envelope + body builders, id/correlation generation (imports `libs/events`).
- `emitter/` — `LocalEmitter` (dev) / `EventBridgeEmitter` (AWS, see §8).
- `emissionlog/` — bounded ring buffer + read/stream.

> Naming note: these are the **LMS Resource APIs** (route group/tag `resources`), not "metadata" — the term reads as "data about data," which obscured that these are the LMS endpoints.

## 3. Event model (`libs/events`)

Canvas Live Events–style `{ metadata, body }` envelope; `metadata` adds `correlation_id` (one per Action run) and `action_id` as additive POC traceability fields. Three event types — `skill_mastered` (`learning_outcome_result_created`), `course_completed` (incl. final grade), `badge_awarded`. No `credential_eligible`. Bodies mirror Canvas where one exists, POC-defined for `badge_awarded`. Every emitted identifier the Context Builder depends on must resolve through the LMS Resource APIs or the related account-user lookup path; the builder fails fast on an unresolvable reference. The producer owns these schemas (source of truth); TS types, if needed, generate into `packages/event-contracts/`.

## 4. Actions & bulk emission

The catalog's top-level object is a **Course**, which *contains* **Actions**. An Action emits 1..N events of one type for **one learner** or **all enrolled learners**. Action availability depends on course kind (standard vs digital-credential-supported) — see [Event Producer §3](../2_requirements/mock-lms-event-producer.md).

Emission control API:

```
POST /demo/courses/{course_id}/actions     # run an Action
  body: { "action": "submit_skill_mastery", "outcome_id": "...", "scope": "one"|"all", "user_id": "..." (when scope=one) }
  → 200 { "correlation_id", "emissions": [ { emission_id, envelope } ... ] }

POST /demo/reset                            # clear emission state for a clean re-run
GET  /demo/courses                          # list courses + the Actions each offers
GET  /demo/emissions?since=<cursor>         # backfill for the UI
GET  /demo/stream                           # SSE live feed (§5)
```

One `correlation_id` per Action run, stamped into every event it emits. A bulk Action emits one event per enrolled learner; each event gets a fresh `event_id`.

## 5. Real-time feed (SSE)

The live feed uses **Server-Sent Events** (`GET /demo/stream`): the lightest transport that gives a genuine real-time, multi-viewer stream (presenter + audience screens), and it composes with static S3+CloudFront hosting. The handler tails the in-memory emission log by cursor and pushes an `emission` event per new record, with periodic keepalives; `GET /demo/emissions?since=` provides backfill. The triggering client may optimistically echo its own emission and reconcile by `emission_id`. (API Gateway WebSockets remain a documented upgrade path if robust multi-client fan-out is later needed.)

## 6. UI design (`apps/mock-lms`)

Course-centric console (see [UI requirements](../2_requirements/mock-lms-ui.md)): pick a course → view modules → Action buttons in context (skill-mastery at the relevant module; final-grade/award-badge at the course level), each runnable for one or all learners. A live SSE timeline shows emissions with raw-envelope view and copyable correlation ids. Static SPA on S3 + CloudFront.

## 7. Data: generate → capture → replay

A **seeded Faker generator** (`mock-lms-generate`) builds the catalog with deterministic, **logically linked ids** (course → modules → outcomes → aligned assignments → submissions → results), guarantees a primary happy path, and uses no wall-clock — so a given seed yields byte-identical output. Its output is **captured to committed `fixtures/*.json`**; the runtime loads that frozen snapshot read-only and never runs the generator. `MOCK_LMS_FIXTURES_DIR` can point at a larger generated set in gitignored `generated-fixtures/`.

This gives two repeatability guarantees: source data identical every run (frozen snapshot → deterministic APIs), and emitted events fresh-id'd per run over stable business keys.

## 8. Local vs AWS

The bus is behind an `Emitter` interface: `LocalEmitter` captures envelopes in-process (dev/tests, no AWS); `EventBridgeEmitter` does `PutEvents` and deploys as the FastAPI service on Lambda behind API Gateway. The same abstraction lets tests assert on emitted envelopes without a bus. (Infra via CDK — not yet built.)

## 9. Auth

CloudFront-layer per ADR-0002 (decided — Cognito was considered and not chosen), resolved in a single dependency so the issuer could change cheaply if that ever changes. A **single demo user** with full capability — no instructor/admin split (it added no functionality for the POC).

## 10. Build order

1. `libs/events`: envelope + 3 event-type schemas.
2. `services/mock-lms`: catalog + generator + LMS Resource APIs + `LocalEmitter` + emission API (Actions).
3. Seed catalog: both course kinds, multiple learners.
4. SSE feed + emission log.
5. `apps/mock-lms`: course view → Action triggers → live timeline.
6. `EventBridgeEmitter` + CDK infra; deploy.
7. CloudFront-layer auth (ADR-0002).

## 11. Testing

Per the pyramid (AGENTS.md): unit tests for builders/schemas/catalog; API tests (FastAPI `TestClient`) for the Resource APIs and emission/Actions; happy-path e2e (Playwright) only. `LocalEmitter` captures envelopes so emission tests need no bus. Generator tests assert determinism + the guaranteed happy path. Tooling: `pytest`, `ruff`, `mypy --strict` (per AGENTS.md).

## 12. Persistence

- **Catalog:** built from the committed snapshot at startup; in-memory, read-only.
- **Emission log:** in-memory ring (live feed) + optional DynamoDB for replay (matches the AWS diagram's store; in-memory suffices for the POC).

Generated artifacts (`audit-output/`, `execution-traces/`, `logs/`, `*.db`, `generated-fixtures/`) stay gitignored per AGENTS.md; the canonical `fixtures/` snapshot is committed.
