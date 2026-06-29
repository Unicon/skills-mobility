# Admin UI — Design

Status: Draft
Date: 2026-06-25
Related: [Requirements](../2_requirements/admin-ui.md) · [Mock LMS Design](./mock-lms.md) · [Orchestrator Design](./orchestrator.md) · [Event Consumer Design](./event-consumer.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0001](../decisions/0001-repo-structure.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0018](../decisions/0018-admin-ui-frontend-stack.md)

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
                                 │ poll read API              │ JSON (execution read model)
                                 ▼                            │
┌──────────────────── services/orchestrator (FastAPI) ────────┴────────────┐
│  GET /executions            (list — prerequisite, §3)                      │
│  GET /executions/{id}       (execution read model: status, gate, steps, result)   │
│  GET /executions?correlation_id=…  (pivot lookup — prerequisite, §3)       │
│        └── reads ──► SQLite execution store (workflow_execution, _step_…)   │
└───────────────────────────────────────────────────────────────────────────┘
        ▲ POST /run-workflow (Event Consumer handoff; also returns the same view synchronously)
```

## 2. Architecture

### Data flow

The Orchestrator executes a run (planner path → executor path, [Orchestrator design §8](./orchestrator.md)) and persists `workflow_execution` + `workflow_step_execution` rows. The Admin UI does not participate in execution; it reads the persisted result:

1. The operator opens the Admin UI → it **polls** the list endpoint for recent executions.
2. The operator selects a workflow (or pastes a `correlation_id`) → the UI fetches that execution's read model.
3. While the workflow is non-terminal, the UI re-fetches on an interval until `status` is `completed`/`failed`.
4. Selecting a step renders its detail from the already-fetched read model's `steps[]` — no extra request.

### Same-origin dev proxy

Like `apps/mock-lms`, the dev server proxies API paths to the backend so the SPA is same-origin in development. Vite proxies the Orchestrator read routes (e.g. `/executions`, `/healthz`) to the local Orchestrator (`:8300`). In production the SPA is static on S3 + CloudFront and reaches the Orchestrator read API through the same edge.

### Why polling now, and designed to become SSE

Polling is the lightest transport that works against static S3 + CloudFront hosting and a synchronous Orchestrator that already returns the whole execution read model per fetch. Because Phase 1 runs the workflow synchronously, a freshly triggered workflow is already terminal by the time the operator pivots to it — there is no incremental progress to stream, so SSE would earn nothing yet while still requiring an event source on the Orchestrator and an unresolved long-lived-connection story on Lambda + CloudFront.

So the MVP polls **deliberately, behind a seam built for the swap.** The UI consumes executions through a single subscription abstraction (§4); polling is its first implementation. The clean trigger to adopt **SSE** is when the Orchestrator moves to the [ADR-0015](../decisions/0015-orchestrator-execution-model.md) queue-driven planner/executor split and emits per-step progress — at that point execution is asynchronous, a workflow is *worth* watching as it advances, and SSE (server→client only, plain HTTP, composes with static hosting) becomes the natural upgrade. The work below is structured so that swap is a single-file change that never touches the views. WebSockets remain a further option only if robust multi-client fan-out is later needed; the Admin UI is read-only, so SSE is the expected target.

## 3. Data contract

The per-workflow and per-step views render the Orchestrator's **execution read model** (`GET /executions/{execution_id}`) — its execution-logs metadata, whose concrete type name is still being settled in the Orchestrator, so this doc refers to it generically:

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

Two shapes in that example are **MVP-only and grow** with the orchestration model:

- **`gate_decision` → a decision-artifact collection.** Phase 1 records only the pre-target gate. The contract is rendered as a collection (FR-AU-11) so it can hold the target audit set — selected delivery targets, the delivery-phase plan with confidence/rationale, policy-validation results, per-decision model/prompt metadata, delivery results. Per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) Workflow Actions is two-stage, so a continue-path run yields *two* Workflow Actions artifacts, not one.
- **`StepResult` has no `inputs`.** The implemented step record carries `output`/`error`/timing but not the resolved inputs FR-AU-12 requires. The viewer treats inputs as a first-class field once the read model provides them.

### Required read-API additions (prerequisites)

Several endpoints and fields the Admin UI needs do not exist yet (Admin UI [FR-AU-16…18b](../2_requirements/admin-ui.md)). They are stated here as the contract the Orchestrator must provide:

| Need | Proposed shape | Status |
|---|---|---|
| Workflow list (level 1) | `GET /executions?limit=…` → `[{ execution_id, correlation_id, event_type, status, updated_at, step_progress }]`, ordered by `updated_at` desc, default cap (e.g. 50); pagination/filtering deferred (FR-AU-16) | Not yet implemented |
| Correlation-group pivot (FR-AU-8/17) | `GET /executions?correlation_id=…` → **list** of 0..N executions in the group (a bulk Action run fans out to many under one id), not a single record | Not yet implemented |
| `correlation_id` + timestamps in the execution read model | add `correlation_id`, `created_at`, `updated_at` (the store already persists them) | Not yet implemented |
| Resolved step inputs (FR-AU-12/18a) | add `inputs` to `StepResult` — inline for small payloads, artifact ref for large | Not yet implemented |
| Decision-artifact collection (FR-AU-11/18b) | a `decisions[]`/`artifacts[]` collection on the execution read model beyond `gate_decision` | Not yet implemented |

The Admin UI build is gated on these; see [requirements §9](../2_requirements/admin-ui.md). Until they land, the UI can render levels 2–3 against `GET /executions/{id}` by `execution_id`.

## 4. Data subscription model (polling now, SSE-ready)

The views never call `fetch` or own a transport. They consume executions through one **subscription seam** — a small hook/store such as `useExecution(id)` (single workflow) and `useExecutionList()` (the list) — whose contract is *"give me the latest execution read model(s) and tell me when they change."* This is the abstraction the SSE upgrade slots behind; everything else is an implementation detail of the seam, not of the components.

```text
components ── read ──► subscription seam ──► transport adapter
  (list, workflow,        useExecution(id)        polling now ─┐
   step panel)            useExecutionList()       SSE later  ─┴─► Orchestrator read API
```

**Current implementation — polling adapter:**

- The list view polls `GET /executions` on a fixed interval while mounted.
- The per-workflow view fetches `GET /executions/{id}` on open and re-polls **only while `status` is non-terminal**, stopping at `completed`/`failed` (Admin UI FR-AU-15).
- Step detail reads from the in-memory read model's `steps[]`; no per-step request.
- Interval is a single tunable constant (target a few seconds, NFR-AU-2); kept conservative since Phase 1 runs are effectively instantaneous.

**The upgrade is contained to the adapter.** When the Orchestrator adopts the [ADR-0015](../decisions/0015-orchestrator-execution-model.md) async worker model and emits per-step progress, the seam grows an SSE adapter (an `EventSource` on a new `GET /executions/{id}/stream`, with the existing `GET` as initial-state + reconnect backfill). The hook contract — an execution read model that updates over time — is unchanged, so no component, view-model, or test that consumes the seam is touched. Until then, the polling adapter satisfies the same contract. This is the one place a transport decision lives, and it is deliberately drawn so the decision can change later without rippling outward.

## 5. UI architecture and design system

Per [ADR-0018](../decisions/0018-admin-ui-frontend-stack.md):

- **Animation:** **Motion** (`framer-motion` / `motion/react`) — MIT-licensed and free; only the separate Motion+ product is paid and is not needed. Same library `apps/mock-lms` already uses.
- **Components:** **Radix Primitives** (headless) styled with our own CSS. **Base UI** is an acceptable alternative primitive layer on a per-component basis. No component framework owns the visual layer — our CSS does.
- **Explicitly not used:** **shadcn/ui** and **Tailwind**. Styling is plain CSS driven by design tokens.

This keeps the Admin UI consistent with the Mock LMS's hand-authored CSS aesthetic while adding accessible, unstyled behavior primitives (dialogs, popovers, tabs) that the Mock LMS built by hand.

## 6. Token architecture

A three-layer token system, consumed by both apps and (later) Figma — the layer through which the "mission-control" identity is preserved rather than re-invented ([ADR-0018](../decisions/0018-admin-ui-frontend-stack.md)):

1. **Base / primitive** — [Open Props](https://open-props.style) scales (spacing, sizing, type scale, radii, shadows, easings) + [Radix Colors](https://www.radix-ui.com/colors) 12-step light/dark scales. Both are free, pure CSS variables, no Tailwind. Open Props fills what the Mock LMS lacks today (it hand-rolls a handful of values); Radix Colors supplies systematic color ramps.
2. **Semantic** — our names, mapped onto the base layer: `--bg`, `--panel`, `--gold`, `--live`, the event-type telemetry colors `--evt-*`, and the scale aliases `--space-*`, `--radius-*`, `--text-*`. This is the contract components and both apps consume.
3. **Component** — component-local variables that reference the semantic layer.

The current Mock LMS [`index.css`](../../apps/mock-lms/src/index.css) is the **de-facto semantic token source**: warm near-black panels (`--bg`/`--panel`), the gold credential signal (`--gold`/`--gold-bright`), live-green status (`--live`), per-event telemetry colors (`--evt-skill`/`--evt-course`/`--evt-badge`/`--evt-credential`), `--danger`, the Archivo + JetBrains Mono pairing, and motifs like the pulsing live `.dot`, the `.copyable` affordance, and the JSON `pre` highlighting. The Admin UI re-expresses these through the shared semantic layer; the mission-control look is the throughline, applied to a workflow-timeline surface instead of a course console.

Mapping the Admin UI's domain onto the existing palette: workflow/step `status` reuses `--live` (succeeded/completed), `--danger` (failed), and dim ink (pending/skipped); `event_type` reuses the `--evt-*` colors so a workflow's type reads the same here as its emission did in the Mock LMS.

## 7. Shared-code plan

Two shared packages are introduced under `packages/` ([ADR-0001](../decisions/0001-repo-structure.md) dependency rules: `apps/` may depend on `packages/`):

- **`packages/ui`** — the shared design tokens (the three layers above) plus shared primitives, notably the **JSON/envelope viewer**, the **event-type color** mapping, and the **copyable correlation-id** affordance — all currently living only inside `apps/mock-lms`. These are **re-authored for accessibility on extraction, not lifted verbatim** (NFR-AU-5): the Mock LMS copyable id is a clickable `span`, so the shared version becomes a real `<button>` (keyboard-operable, visible copy-failure feedback), and the JSON viewer must degrade gracefully on malformed or very large payloads (FR-AU-22).
- **`packages/contracts`** — shared TypeScript types and typed API clients (the execution-read-model / `StepResult` shapes here; the emission/envelope shapes for the Mock LMS), giving both apps one source of truth for backend contracts.

The actual extraction of these packages and the migration of `apps/mock-lms` onto them is **implementation work, deferred to a later round** (after these specs merge). This design records the target so the Admin UI is built against it rather than duplicating Mock LMS code that later has to be un-duplicated.

## 8. Information architecture and layout

Three levels (Admin UI [§3](../2_requirements/admin-ui.md)), with steps as master-detail inside the workflow view:

- **Workflow list** — a table/rail of recent executions: `correlation_id` (copyable), `event_type` (telemetry-colored), `status` (incl. a distinct `failed` treatment, FR-AU-23), a timestamp, and step progress. A **correlation-id input** at the top accepts an id pasted from the Mock LMS and resolves it to its correlation group: one match opens the workflow, several scope the list to the group, none shows an empty state (FR-AU-8). Polls the list endpoint.
- **Per-workflow detail** — header band (status, `event_type`, copyable `execution_id` + `correlation_id`, `plan_id`, final outcome); a **decision-artifacts panel** rendering the recorded artifacts as a collection (Phase 1: the gate decision's `decision` / `confidence` / `rationale`; later, the delivery-target/plan/policy/model artifacts of FR-AU-11) as the reasoning log; and the **ordered step timeline**, each row showing `action_id`, `status`, and timing, with the failing step highlighted for a `failed` run.
- **Per-step detail** — selecting a step row opens a side panel (Radix Dialog/Collapsible — focus-trapped and keyboard-operable per NFR-AU-5) with the step's resolved inputs, raw `output` JSON (shared viewer), `error`, `attempt`, and timing. The decision artifacts and final `result` are inspectable as raw JSON the same way.
- **Cross-cutting states** — every level has defined empty/error/loading states (FR-AU-22): empty list, unreachable/erroring read API, no-match and many-match pivots, and graceful handling of malformed or oversized JSON in the viewer.

## 9. Local vs AWS, and auth

- **Local:** Vite dev server proxies the Orchestrator read routes to `:8300`, same-origin like `apps/mock-lms`. The Orchestrator serves from SQLite ([ADR-0014](../decisions/0014-poc-storage-strategy.md)).
- **AWS:** static SPA on S3 + CloudFront ([ADR-0002](../decisions/0002-frontend-architecture.md)); the read API is the Orchestrator's deployed read surface (DynamoDB-backed store per ADR-0014 in the AWS-shaped target). The subscription seam's polling adapter is unchanged; an SSE adapter would additionally need a long-lived-connection-capable surface (an open item for the async-execution phase, §4).
- **Auth:** CloudFront-layer per [ADR-0002](../decisions/0002-frontend-architecture.md), resolved behind a single boundary; a single demo user with full read capability, no role split.

## 10. Build order

1. `packages/contracts`: the execution-read-model / `StepResult` TS types + a typed Orchestrator read client. *(Depends on the prerequisite read-API additions, §3.)*
2. `packages/ui`: extract tokens (three layers) + the JSON viewer, event-type colors, and copyable-id primitive from `apps/mock-lms`; migrate `apps/mock-lms` onto them.
3. `apps/admin` scaffold: Vite + React + the shared packages + same-origin dev proxy.
4. The subscription seam (`useExecution`/`useExecutionList`, §4) with its polling adapter and terminal-state stop — established before the views so every feature consumes the seam, not a transport.
5. Workflow list + correlation-id pivot (against the list / lookup endpoints).
6. Per-workflow detail: header, gate-decision panel, step timeline.
7. Per-step detail panel + raw JSON viewer.
8. CloudFront-layer auth + S3/CloudFront deploy ([ADR-0002](../decisions/0002-frontend-architecture.md)).
9. *(Later, gated on async Orchestrator execution)* SSE adapter behind the same seam — see §4.

Steps 1–2 (`packages/*` extraction and the `apps/admin` scaffold) are gated on these specs merging and the Orchestrator read-API prerequisites; they are **not** part of the specs PR.

## 11. Testing

Per the pyramid ([AGENTS.md](../../AGENTS.md)):

- **Unit** — the subscription seam and its polling adapter (terminal-state stop, list reconciliation) tested against the hook contract so an SSE adapter can later reuse the same tests; the status→token mapping; and the shared JSON viewer / event-type color helpers in `packages/ui`.
- **Integration** — the typed read client in `packages/contracts` against a faked Orchestrator read API (fixture execution read models), including the not-found and correlation-pivot paths.
- **End-to-end (Playwright)** — happy path only: trigger a workflow (or seed an execution), pivot by `correlation_id`, open the workflow, expand a step, view raw JSON. No exhaustive corner cases.

Tests use fixture execution read models rather than a live Orchestrator, consistent with the deterministic-fixtures approach used elsewhere in the repo.
