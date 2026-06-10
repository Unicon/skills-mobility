# Mock Event Producer — Design

Status: Draft
Date: 2026-06-10
Related: [Requirements](../2_requirements/mock-event-producer.md) · [POC Requirements](../2_requirements/poc-requirements.md) · [ADR-0001](../decisions/0001-repo-structure.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0003](../decisions/0003-programming-language.md)

## 1. Overview

The Mock Event Producer ("Mock LMS") is composed of three deployable/buildable units, placed per ADR-0001's monorepo layout:

| Unit | Path | Tech (ADR-0003) | Role |
|---|---|---|---|
| Mock LMS service | `services/mock-lms/` | Python 3.12 + FastAPI + Pydantic | Canvas-style read APIs + event emission control API |
| Mock LMS UI | `apps/mock-lms/` | React + TypeScript SPA | Inspect data, trigger events, live emission log/visualization |
| Shared event contracts | `libs/events/` (Py) + optionally `packages/event-contracts/` (TS) | Pydantic / generated TS types | Event names, envelope, body schemas — the producer is source of truth |

The service is the **only** component that writes to the event bus; the UI talks **only** to the service. The Context Builder (downstream, separate component) reads the Canvas-style APIs directly.

```
┌──────────────────────────── apps/mock-lms (React SPA, S3+CloudFront) ────────────────────────────┐
│  Inspect (browse scenario data)   Trigger (emit event / run scenario)   Live log + visualization   │
└───────────────┬───────────────────────────────┬──────────────────────────────▲────────────────────┘
                │ GET Canvas-style metadata        │ POST emit / run-scenario     │ live emissions (WS/SSE)
                ▼                                  ▼                              │
┌──────────────────────────────── services/mock-lms (FastAPI) ──────────────────┴────────────────────┐
│  Metadata API  ──reads──►  Scenario Store (seeded fixtures, in-memory/SQLite)                        │
│  Emission API  ──build envelope──►  Emitter  ──PutEvents──►  Amazon EventBridge                      │
│  Emission API  ──record──►  Emission Log (in-memory ring + optional DynamoDB/SQLite)  ──►  WS/SSE hub │
└────────────────────────────────────────────────────────┬───────────────────────────────────────────┘
                                                          ▼
                                          EventBridge → Event Consumer (Lambda) → Step Functions
                                                          (downstream, separate components)
```

## 2. Service design (`services/mock-lms`)

### 2.1 Modules

- `api/metadata/` — Canvas-style read routers (one router per resource: courses, enrollments, modules, pages, assignments, outcomes, outcome_results, outcome_alignments, submissions).
- `api/emit/` — emission control endpoints (single event, run scenario, reset).
- `api/stream/` — WebSocket/SSE endpoint for the live emission feed.
- `scenarios/` — scenario loader + the in-memory/SQLite scenario store.
- `events/` — envelope builder, event-type body builders, id/correlation generation (imports schemas from `libs/events`).
- `emitter/` — bus adapter (`EventBridgeEmitter` for AWS, `LocalEmitter` for dev — see §6).
- `emissionlog/` — append + query + pub/sub fan-out to stream subscribers.

### 2.2 Emission control API (UI-facing)

```
POST /demo/emit
  body: { "event_type": "skill_mastered", "course_id": "...", "user_id": "...",
          "outcome_id": "...", "assignment_id": "..." (as relevant) }
  → 200 { "emission_id", "correlation_id", "envelope": { metadata, body } }

POST /demo/scenarios/{scenario_id}/run
  body: { "delay_ms": 0 }   # optional inter-event pacing
  → 200 { "run_id", "correlation_id", "emissions": [ { emission_id, envelope } ... ] }

POST /demo/scenarios/{scenario_id}/reset   → 200
GET  /demo/scenarios                         → list available scenarios + metadata
GET  /demo/emissions?since=<cursor>          → recent emissions (log backfill for the UI)
GET  /demo/stream                            → WebSocket/SSE live feed (§4)
```

Notes:
- `correlation_id` is generated per trigger (per single emit, or per scenario run) and stamped into every envelope's `metadata`.
- `emission_id` and event `metadata.event_id` are unique per emission (satisfies FR-E4 idempotency-friendliness; re-running a scenario yields fresh ids over stable business keys).

### 2.3 Canvas-style metadata API

Routers implement exactly the paths in requirements §5.3, returning Pydantic-modeled, Canvas-shaped responses served from the active scenario's store. Responses are deterministic per scenario (NFR-5). Unknown ids → Canvas-style `404`. Business-friendly lookups (get badge/skill/course by id) are thin views over the same store.

A FastAPI dependency selects the **active scenario** (default scenario, or per-request override via header/query for multi-scenario demos), keeping the metadata responses consistent with whatever the UI is currently inspecting.

## 3. Event model (`libs/events`)

### 3.1 Envelope

Canvas Live Events–style `{ metadata, body }` (requirements §5.2). `metadata` adds two POC traceability fields — `correlation_id` and `scenario_id` — beyond the Canvas-standard fields. These are additive and ignored by anything expecting vanilla Canvas events.

### 3.2 Event types → body shapes

| Event type | Modeled on | Body source of truth | Maps to happy path |
|---|---|---|---|
| `skill_mastered` | Canvas `learning_outcome_result_created` | Canvas outcome-result body | Skill Mastered |
| `course_completed` | Canvas `course_completed` | Canvas course body | Course Completed |
| `badge_awarded` | POC-defined | documented here | Badge Awarded |
| `credential_eligible` | POC-defined | documented here | (open Q — see req §11.4) |

Every id in a body (course/user/outcome/assignment) MUST resolve against the metadata APIs (FR-P3). The envelope builder validates this at emit time in dev (fail fast if a scenario references an unknown id).

### 3.3 Contract ownership

The producer is the **source of truth** for event names and schemas. Python models live in `libs/events`; if/when the Event Consumer or Admin app needs TS types, generate them into `packages/event-contracts/` from the Pydantic models (ADR-0001 flags cross-language contract ownership as a deferred decision — this records the producer's stance for the events it owns).

## 4. Real-time emission feed (the "live demo" requirement)

Requirement FR-U5/FR-U6 and NFR-4 want emissions visible in the UI within ~1s. Three options:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. Optimistic client append** | UI appends the synchronous `POST /demo/emit` response to its own timeline | Zero extra infra; works offline | Single-client only; no cross-tab/presenter-screen sync; not a true "stream" |
| **B. SSE** (`GET /demo/stream`) | Server pushes emission events over a long-lived HTTP stream | Simple, fits FastAPI, one-way is all we need, CloudFront-friendly | Server must hold connections; reconnect handling |
| **C. API Gateway WebSocket** | AWS-native bidirectional socket | Most "production-shaped"; multi-client | Most infra/auth wiring for a POC |

**Recommendation:** **B (SSE)** as the primary live feed — it's the lightest transport that gives a genuine real-time multi-viewer stream (good for a presenter screen + audience screen), and it composes with the static S3+CloudFront hosting model. Combine with **A** as an instant optimistic echo so the triggering client feels no latency, and reconcile against the SSE feed by `emission_id`. Keep **C** as the documented upgrade path if the sales demo needs robust multi-client fan-out or the WS infra already exists.

The emission log keeps a bounded in-memory ring buffer for the live feed and (optionally) persists to DynamoDB/SQLite for replay/backfill via `GET /demo/emissions?since=`.

## 5. UI design (`apps/mock-lms`)

Three-pane demo console:

1. **Scenario rail** — pick scenario, run, reset; shows scenario description (the demo narrative).
2. **Inspector** — browse the active scenario's course → modules → assignments → students → outcomes → outcome results → submissions, each fetched from the Canvas-style metadata APIs (so the UI exercises the same surface the Context Builder uses). Instructor view scopes to "their" course; admin view sees all.
3. **Emission timeline** — live log (SSE) of emissions: type, time, correlation id (copyable, FR-U7), target; click an entry to see the raw envelope JSON (FR-U4). Most-recent highlighted; presentable as a horizontal flow strip for an audience (FR-U6).

Trigger affordances live in the Inspector (e.g. a "Grade last assignment" / "Mark course complete" button on the relevant entity) and in the Scenario rail (run whole scenario). Per requirements §6.2, these are triggers, not data mutations.

The build is a static SPA deployed to S3 + CloudFront (ADR-0002).

## 6. Local dev vs AWS

Per ADR-0003 the workload is I/O-bound and serverless-targeted. The bus is abstracted behind an `Emitter` interface:

- `LocalEmitter` — writes to an in-process queue / local file / local stand-in; lets the whole producer run with no AWS account (CLAUDE.md notes `generated-fixtures/`, local DBs are gitignored). Canonical scenario fixtures, however, are **checked in** (they define the demo).
- `EventBridgeEmitter` — `PutEvents` to the configured bus; deployed as the FastAPI service on Lambda (e.g. via an ASGI adapter) behind API Gateway, per the AWS architecture diagram.

Same abstraction lets tests assert on emitted envelopes without a bus.

## 7. Auth (CloudFront-layer, per ADR-0002)

The POC uses **CloudFront-layer auth** (requirements §7): the UI logs in directly as a role and the service trusts an injected role claim (instructor/admin). No Cognito user pool.

The service reads role from a single `get_current_role()` dependency that, for the POC, resolves the role from the CloudFront-injected claim/header. Keeping role resolution in one dependency means a hypothetical future issuer change (e.g. Cognito) would be contained to that dependency rather than spread across handlers — but that is not in scope; the implemented path is CloudFront-layer auth.

## 8. Persistence

- **Scenario store:** seeded from version-controlled fixtures at startup; in-memory by default, SQLite optional for convenience. Read-only at runtime (FR-A1).
- **Emission log:** in-memory ring (live feed) + optional DynamoDB/SQLite for replay. DynamoDB matches the AWS diagram's store for the broader system; for the POC, SQLite/in-memory is sufficient.

Generated artifacts (`audit-output/`, `execution-traces/`, `logs/`, `*.db`) stay gitignored per CLAUDE.md; canonical scenario fixtures are committed.

## 9. Testing

- **Schema tests:** every event-type builder produces an envelope that validates against `libs/events` models; every body id resolves against the metadata store.
- **Metadata API tests:** Canvas-shaped responses, deterministic per scenario, Canvas-style 404s.
- **Emission tests:** `LocalEmitter` captures envelopes; assert correlation/scenario/event ids and re-run freshness (FR-E4).
- **Scenario tests:** each canonical happy path runs end-to-end against `LocalEmitter` and produces the expected ordered event sequence.
- Tooling per CLAUDE.md: `pytest`, `ruff`, `mypy`, `coverage`.

## 10. Build order (suggested)

1. `libs/events`: envelope + the four event-type schemas.
2. `services/mock-lms`: scenario store + Canvas metadata APIs + `LocalEmitter` + emission API (no UI).
3. Canonical scenarios: Skill Mastered, Course Completed, Badge Awarded.
4. SSE stream + emission log.
5. `apps/mock-lms`: inspector → timeline → triggers.
6. `EventBridgeEmitter` + infra wiring; deploy.
7. CloudFront-layer auth boundary (§7).

Steps 1–4 deliver a demonstrable producer (drive it via API/CLI) before any frontend work, de-risking the event contract early.

## 11. Open design decisions

Mirrors requirements §11 — real-time transport (§4, recommended SSE), whether triggers mutate inspected data (§6.2 / req §6.2), `credential_eligible` ownership (§3.2), and scenario authoring location (in-repo vs Admin UI). Auth is settled: CloudFront-layer per ADR-0002 (§7).
