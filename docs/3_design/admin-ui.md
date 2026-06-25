# Admin UI — Design

Status: Draft
Date: 2026-06-25
Related: [Requirements](../2_requirements/admin-ui.md) · [Mock LMS Design](./mock-lms.md) · [Orchestrator Design](./orchestrator.md) · [Event Consumer Design](./event-consumer.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0001](../decisions/0001-repo-structure.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0017](../decisions/0017-admin-ui-frontend-stack.md)

## 1. Overview

The **Admin UI** is the POC's observability surface over the Orchestrator. It is the downstream pair of the [Mock LMS UI](./mock-lms.md): the presenter triggers a workflow there, copies the run's `correlation_id`, and follows that workflow here.

| Part | Path | Tech | Role |
|---|---|---|---|
| Admin SPA | `apps/admin/` | React + TypeScript + Vite SPA | Workflow list, per-workflow timeline, per-step decision/reasoning view |
| Data source | `services/orchestrator/` (read API) | FastAPI over SQLite ([ADR-0014](../decisions/0014-poc-storage-strategy.md)) | Serves the execution records the Admin UI renders |

The Admin UI is a **read-only client** of the Orchestrator. It owns no store of its own and never writes workflow state. The Orchestrator runs the workflow (mocked end-to-end in Phase 1), persists each run, and serves it back; the Admin UI polls and renders it.

```
┌──────────────── apps/admin (React SPA, S3+CloudFront) ───────────────────┐
│  Workflow list + correlation pivot → per-workflow timeline → step detail   │
└───────────────────────────────┬───────────────────────────▲──────────────┘
                                 │ poll read API              │ JSON (ExecutionView)
                                 ▼                            │
┌──────────────────── services/orchestrator (FastAPI) ────────┴────────────┐
│  GET /executions            (list — prerequisite, §3)                      │
│  GET /executions/{id}       (ExecutionView: status, gate, steps, result)   │
│  GET /executions?correlation_id=…  (pivot lookup — prerequisite, §3)       │
│        └── reads ──► SQLite execution store (workflow_execution, _step_…)   │
└───────────────────────────────────────────────────────────────────────────┘
        ▲ POST /run-workflow (Event Consumer handoff; also returns the same view synchronously)
```

## 2. Architecture

### Data flow

The Orchestrator executes a run (planner path → executor path, [Orchestrator design §8](./orchestrator.md)) and persists `workflow_execution` + `workflow_step_execution` rows. The Admin UI does not participate in execution; it reads the persisted result:

1. The operator opens the Admin UI → it **polls** the list endpoint for recent executions.
2. The operator selects a workflow (or pastes a `correlation_id`) → the UI fetches that execution's `ExecutionView`.
3. While the workflow is non-terminal, the UI re-fetches on an interval until `status` is `completed`/`failed`.
4. Selecting a step renders its detail from the already-fetched `ExecutionView.steps[]` — no extra request.

### Same-origin dev proxy

Like `apps/mock-lms`, the dev server proxies API paths to the backend so the SPA is same-origin in development. Vite proxies the Orchestrator read routes (e.g. `/executions`, `/healthz`) to the local Orchestrator (`:8300`). In production the SPA is static on S3 + CloudFront and reaches the Orchestrator read API through the same edge.

### Why polling (MVP)

Polling is the lightest transport that works against static S3 + CloudFront hosting and a synchronous Orchestrator that already returns the whole `ExecutionView` per fetch. Because Phase 1 runs the workflow synchronously, a freshly triggered workflow is already terminal by the time the operator pivots to it; polling mainly keeps the list current and supports the later case where execution becomes asynchronous (the [ADR-0015](../decisions/0015-orchestrator-execution-model.md) queue-driven planner/executor split). A pub/sub or SSE push channel is the documented upgrade path if real-time freshness is later needed; it is out of scope for the MVP.

## 3. Data contract

The per-workflow and per-step views render the Orchestrator's `ExecutionView` (`GET /executions/{execution_id}`):

```jsonc
{
  "execution_id": "…",
  "event_type": "skill_mastered",
  "status": "completed",          // created | planning | ready | running | completed | failed
  "gate_decision": {               // pre-target Workflow Actions decision (AI-reasoning surface)
    "decision": "continue_to_delivery_targets",
    "confidence": 1.0,
    "rationale": "Deterministic Phase 1 happy-path gate decision."
  },
  "plan_id": "phase1-skill-mastered.v1",
  "steps": [                       // ordered; one per executed step
    {
      "step_id": 1,
      "action_id": "resolve_learncard_profile",
      "status": "succeeded",       // succeeded | skipped | failed
      "attempt": 1,
      "output": { /* opaque per-action JSON */ },
      "error": null,
      "started_at": "…",
      "finished_at": "…"
    }
  ],
  "result": { /* final workflow outcome */ }
}
```

This mirrors the Orchestrator's implemented read model (`GET /executions/{id}`) over its persisted execution state ([Orchestrator design §9](./orchestrator.md)). The `output`, `gate_decision`, and `result` fields are opaque JSON by design ([Orchestrator FR-OR-22](../2_requirements/orchestrator.md)) and are rendered through the shared JSON viewer rather than typed per action.

### Required read-API additions (prerequisites)

Two endpoints and two fields the Admin UI needs do not exist yet (Admin UI [FR-AU-16…18](../2_requirements/admin-ui.md)). They are stated here as the contract the Orchestrator must provide:

| Need | Proposed shape | Status |
|---|---|---|
| Workflow list (level 1) | `GET /executions` → `[{ execution_id, correlation_id, event_type, status, updated_at, step_progress }]` | Not yet implemented |
| Correlation-id pivot (FR-AU-8) | `GET /executions?correlation_id=…` (or `GET /executions/by-correlation/{id}`) → the matching execution | Not yet implemented |
| `correlation_id` + timestamps in `ExecutionView` | add `correlation_id`, `created_at`, `updated_at` (the store already persists them) | Not yet implemented |

The Admin UI build is gated on these; see [requirements §9](../2_requirements/admin-ui.md). Until they land, the UI can render levels 2–3 against `GET /executions/{id}` by `execution_id`.

## 4. Polling model

- The list view polls `GET /executions` on a fixed interval while mounted.
- The per-workflow view fetches `GET /executions/{id}` on open and re-polls **only while `status` is non-terminal**, stopping at `completed`/`failed` (Admin UI FR-AU-15).
- Step detail reads from the in-memory `ExecutionView.steps[]`; no per-step request.
- Interval is a single tunable constant (target a few seconds, NFR-AU-2); kept conservative since Phase 1 runs are effectively instantaneous.
- **Upgrade path:** when the Orchestrator moves to the [ADR-0015](../decisions/0015-orchestrator-execution-model.md) async worker model, replace the per-workflow poll with an SSE/WebSocket subscription behind the same view-model — the component contract (an `ExecutionView` stream) does not change.

## 5. UI architecture and design system

Per [ADR-0017](../decisions/0017-admin-ui-frontend-stack.md):

- **Animation:** **Motion** (`framer-motion` / `motion/react`) — MIT-licensed and free; only the separate Motion+ product is paid and is not needed. Same library `apps/mock-lms` already uses.
- **Components:** **Radix Primitives** (headless) styled with our own CSS. **Base UI** is an acceptable alternative primitive layer on a per-component basis. No component framework owns the visual layer — our CSS does.
- **Explicitly not used:** **shadcn/ui** and **Tailwind**. Styling is plain CSS driven by design tokens.

This keeps the Admin UI consistent with the Mock LMS's hand-authored CSS aesthetic while adding accessible, unstyled behavior primitives (dialogs, popovers, tabs) that the Mock LMS built by hand.

## 6. Token architecture

A three-layer token system, consumed by both apps and (later) Figma — the layer through which the "mission-control" identity is preserved rather than re-invented ([ADR-0017](../decisions/0017-admin-ui-frontend-stack.md)):

1. **Base / primitive** — [Open Props](https://open-props.style) scales (spacing, sizing, type scale, radii, shadows, easings) + [Radix Colors](https://www.radix-ui.com/colors) 12-step light/dark scales. Both are free, pure CSS variables, no Tailwind. Open Props fills what the Mock LMS lacks today (it hand-rolls a handful of values); Radix Colors supplies systematic color ramps.
2. **Semantic** — our names, mapped onto the base layer: `--bg`, `--panel`, `--gold`, `--live`, the event-type telemetry colors `--evt-*`, and the scale aliases `--space-*`, `--radius-*`, `--text-*`. This is the contract components and both apps consume.
3. **Component** — component-local variables that reference the semantic layer.

The current Mock LMS [`index.css`](../../apps/mock-lms/src/index.css) is the **de-facto semantic token source**: warm near-black panels (`--bg`/`--panel`), the gold credential signal (`--gold`/`--gold-bright`), live-green status (`--live`), per-event telemetry colors (`--evt-skill`/`--evt-course`/`--evt-badge`/`--evt-credential`), `--danger`, the Archivo + JetBrains Mono pairing, and motifs like the pulsing live `.dot`, the `.copyable` affordance, and the JSON `pre` highlighting. The Admin UI re-expresses these through the shared semantic layer; the mission-control look is the throughline, applied to a workflow-timeline surface instead of a course console.

Mapping the Admin UI's domain onto the existing palette: workflow/step `status` reuses `--live` (succeeded/completed), `--danger` (failed), and dim ink (pending/skipped); `event_type` reuses the `--evt-*` colors so a workflow's type reads the same here as its emission did in the Mock LMS.

## 7. Shared-code plan

Two shared packages are introduced under `packages/` ([ADR-0001](../decisions/0001-repo-structure.md) dependency rules: `apps/` may depend on `packages/`):

- **`packages/ui`** — the shared design tokens (the three layers above) plus shared primitives, notably the **JSON/envelope viewer**, the **event-type color** mapping, and the **copyable correlation-id** affordance — all currently living only inside `apps/mock-lms`.
- **`packages/contracts`** — shared TypeScript types and typed API clients (the `ExecutionView`/`StepResult` shapes here; the emission/envelope shapes for the Mock LMS), giving both apps one source of truth for backend contracts.

The actual extraction of these packages and the migration of `apps/mock-lms` onto them is **implementation work, deferred to a later round** (after these specs merge). This design records the target so the Admin UI is built against it rather than duplicating Mock LMS code that later has to be un-duplicated.

## 8. Information architecture and layout

Three levels (Admin UI [§3](../2_requirements/admin-ui.md)), with steps as master-detail inside the workflow view:

- **Workflow list** — a table/rail of recent executions: `correlation_id` (copyable), `event_type` (telemetry-colored), `status`, a timestamp, and step progress. A **correlation-id input** at the top accepts an id pasted from the Mock LMS and navigates to that workflow (FR-AU-8). Polls the list endpoint.
- **Per-workflow detail** — header band (status, `event_type`, copyable `execution_id` + `correlation_id`, `plan_id`, final outcome); a **gate-decision panel** showing `decision` / `confidence` / `rationale` as the reasoning log; and the **ordered step timeline**, each row showing `action_id`, `status`, and timing, visually echoing the Mock LMS emission timeline.
- **Per-step detail** — selecting a step row opens a side panel (Radix Dialog/Collapsible) with the step's resolved inputs, raw `output` JSON (shared viewer), `error`, `attempt`, and timing. The gate decision and final `result` are inspectable as raw JSON the same way.

## 9. Local vs AWS, and auth

- **Local:** Vite dev server proxies the Orchestrator read routes to `:8300`, same-origin like `apps/mock-lms`. The Orchestrator serves from SQLite ([ADR-0014](../decisions/0014-poc-storage-strategy.md)).
- **AWS:** static SPA on S3 + CloudFront ([ADR-0002](../decisions/0002-frontend-architecture.md)); the read API is the Orchestrator's deployed read surface (DynamoDB-backed store per ADR-0014 in the AWS-shaped target). The polling client is unchanged.
- **Auth:** CloudFront-layer per [ADR-0002](../decisions/0002-frontend-architecture.md), resolved behind a single boundary; a single demo user with full read capability, no role split.

## 10. Build order

1. `packages/contracts`: the `ExecutionView`/`StepResult` TS types + a typed Orchestrator read client. *(Depends on the prerequisite read-API additions, §3.)*
2. `packages/ui`: extract tokens (three layers) + the JSON viewer, event-type colors, and copyable-id primitive from `apps/mock-lms`; migrate `apps/mock-lms` onto them.
3. `apps/admin` scaffold: Vite + React + the shared packages + same-origin dev proxy.
4. Workflow list + correlation-id pivot (against the list / lookup endpoints).
5. Per-workflow detail: header, gate-decision panel, step timeline.
6. Per-step detail panel + raw JSON viewer.
7. Polling/refresh with terminal-state stop.
8. CloudFront-layer auth + S3/CloudFront deploy ([ADR-0002](../decisions/0002-frontend-architecture.md)).

Steps 1–2 (`packages/*` extraction and the `apps/admin` scaffold) are gated on these specs merging and the Orchestrator read-API prerequisites; they are **not** part of the specs PR.

## 11. Testing

Per the pyramid ([AGENTS.md](../../AGENTS.md)):

- **Unit** — the view-model/polling logic (terminal-state stop, list reconciliation), the status→token mapping, and the shared JSON viewer / event-type color helpers in `packages/ui`.
- **Integration** — the typed read client in `packages/contracts` against a faked Orchestrator read API (fixture `ExecutionView`s), including the not-found and correlation-pivot paths.
- **End-to-end (Playwright)** — happy path only: trigger a workflow (or seed an execution), pivot by `correlation_id`, open the workflow, expand a step, view raw JSON. No exhaustive corner cases.

Tests use fixture `ExecutionView`s rather than a live Orchestrator, consistent with the deterministic-fixtures approach used elsewhere in the repo.
