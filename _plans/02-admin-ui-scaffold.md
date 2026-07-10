---
status: Active
---

# Plan 2 — Scaffold + stub `apps/admin` on the shared packages

> Plan 2 of 2. **Depends on Plan 1** (`01-frontend-workspace-and-mock-lms.md`): the
> npm workspace and the `@skills-mobility/ui` + `@skills-mobility/contracts` packages
> must exist first. **Plan 1 is merged to `main`** (PR #70), so this plan branches
> directly off `main` rather than stacking on Plan 1's now-merged branch.

## Clarifying Questions & Answers

Reconnaissance (via the `Explore` sub-agent, plus direct reads of the Orchestrator
schemas/routes, ADR-0018/0020, the admin-ui requirements/design docs, and GitHub
issue #71) confirmed Plan 2's factual claims — Plan 1 fully merged, PR #32's
`GET /executions` and PR #22's `GET /executions/{id}` both live on `main`,
`EnvelopeModal` genuinely lacking dialog semantics, Radix primitives genuinely
absent from the workspace — and surfaced four decisions before implementation:

1. ADR-0020 (Accepted) says apps keep unscoped names (`mock-lms-ui`, `admin-ui`),
   but this plan's draft text named the new package `@skills-mobility/admin`
   (scoped) — a direct conflict. Which should the package be named?
   **Answer:** `admin-ui` (recommended option) — per the Accepted ADR and the
   `mock-lms-ui` precedent; the plan's scoped name was an imprecise draft, not an
   intentional override.
2. Design doc §8 calls the per-step detail panel a "side panel (Radix
   Dialog/Collapsible)" while requirements §3 frames it as master-detail "within
   the per-workflow view, not as a separate page" — pulling toward different
   Radix primitives. Dialog (modal overlay) or Collapsible (inline panel)?
   **Answer:** Radix `Collapsible` (inline panel, recommended option) — matches
   "master-detail, not a separate page" literally; docked in the workflow-detail
   layout, no overlay.
3. The plan's text says "stacked on Plan 1's branch," but Plan 1 is already
   merged to `main`. Branch base and worktree choice?
   **Answer:** Branch off `main` (`feat/admin-ui-scaffold`), main checkout, no
   worktree (recommended option) — no other parallel work in flight, so a
   worktree adds overhead without benefit.
4. Four smaller carried-forward assumptions, bundled into one confirmation:
   NOJIRA tracking (same as Plan 1 — no Jira/INT-board integration in this
   repo); a single tunable 3000ms polling interval (NFR-AU-2 says "a few
   seconds," no exact value mandated); `ExecutionMetadata.gate_decision` typed
   client-side as `GateDecision | null` (a narrowing choice over the wire's
   untyped `dict`, matching design §3's framing); and the `EnvelopeModal` Radix
   fix (issue #71) landing in this same branch, as this plan already directs.
   **Answer:** Proceed with all four (recommended option) — no changes.

Decisions 1–3 resolve real ambiguities/conflicts in this plan's own text (not
pure confirmations of stated defaults), so a plan-approval pause followed with
the updated plan below; the developer approved it with no further amendments.

## Context

The Admin UI is the read-only observability pair of the Mock LMS console: a presenter
triggers a workflow in the Mock LMS, copies its `correlation_id`, then follows that run
in the Admin UI to see how the Orchestrator planned and executed it. It's fully specced
in [admin-ui requirements](../docs/2_requirements/admin-ui.md) /
[design](../docs/3_design/admin-ui.md); stack per
[ADR-0018](../docs/decisions/0018-admin-ui-frontend-stack.md), workspace per
[ADR-0020](../docs/decisions/0020-js-ts-workspace-tooling.md). Docs name the app
`apps/admin`.

**Carried over from Plan 1's PR review:** [#71](https://github.com/Unicon/skills-mobility/issues/71)
— `packages/ui`'s `EnvelopeModal` has no dialog semantics (no `role="dialog"`/
`aria-modal`, no Escape-to-close, no focus trap/restore), flagged in review of
PR #70 (NFR-AU-5). Deliberately deferred to this plan rather than #70, since
this is where Radix Primitives actually enter the workspace (step 2 below) —
wrap `EnvelopeModal` in Radix's `Dialog` primitive as part of that step instead
of hand-rolling focus-trap logic in Plan 1. Do not let this plan land without
resolving #71 alongside the Radix Primitives introduction.

Backend it reads — the **Orchestrator** (default port **8400**,
`services/orchestrator/src/orchestrator/config.py:16`):
- `GET /executions/{id}` — **on `main`** (via #22; carries `correlation_id`/timestamps).
  Backs the detail + step views (levels 2–3). **Live now.**
- `GET /executions?limit=&correlation_id=` — level-1 list/pivot, returning
  `ExecutionSummary` rows. **Merged to `main` via PR #32** — fully live now, so all
  three levels can be verified end-to-end against a local orchestrator.

## Goal

Stand up `apps/admin` as a workspace member consuming the shared packages, with the
three view levels stubbed and wired to real data wherever the backend already supports it.

## Steps

### 1. Extend `packages/contracts` with the execution read model (design §7 step 1)

Plan 1 created `packages/contracts` with the Mock-LMS half. Add the **Admin-UI half**
here — now verifiable live since PR #32 is on `main`:

- **Types** derived (client-side, not backend-imported) from the Orchestrator read
  model ([services/orchestrator/src/orchestrator/schemas.py](../services/orchestrator/src/orchestrator/schemas.py)):
  - `ExecutionSummary` — `{execution_id, correlation_id, event_type, status,
    step_progress:{completed,total}, created_at, updated_at}`.
  - `ExecutionMetadata` — summary fields + `gate_decision`, `plan_id`,
    `steps: StepResult[]`, `result`.
  - `StepResult` — `{step_id, action_id, status(succeeded|skipped|failed), attempt,
    output, error, started_at, finished_at}`.
  - `GateDecision`; `status` union `created|planning|ready|running|completed|failed`.
- **Typed Orchestrator read client** reusing the thin `fetch` wrapper Plan 1 moved into
  contracts: `listExecutions({limit, correlationId})` → `GET /executions`;
  `getExecution(id)` → `GET /executions/{id}`.
- **Tests (design §8 integration):** the client against a **faked** Orchestrator
  (fixture read models via injected fetch/transport) — happy path, not-found,
  correlation-pivot.

### 2. Scaffold `apps/admin` (ADR-0018 / design §5)

- Workspace member: `package.json` (name **`admin-ui`**, unscoped per ADR-0020;
  React 19 + Vite + `@radix-ui/react-dialog` + `@radix-ui/react-collapsible` +
  `motion` + `@skills-mobility/ui`/`contracts` as `"*"`), `tsconfig.json`,
  `index.html`, `src/main.tsx`, `vite.config.ts`.
- **While `@radix-ui/react-dialog` is being added here, also
  resolve [#71](https://github.com/Unicon/skills-mobility/issues/71):** wrap
  `packages/ui`'s `EnvelopeModal` in the Radix `Dialog` primitive instead of its
  current bare scrim `<div>`, so it gets `role="dialog"`/`aria-modal`,
  Escape-to-close, and focus trap/restore for free — both apps pick up the fix
  since it's a shared primitive.
- **Vite proxy → Orchestrator `http://127.0.0.1:8400`** (`/executions`, `/healthz`);
  dev server on a free port (e.g. 5174). (This is the Orchestrator, **not** mock-lms's :8000.)
- Import tokens/global CSS from `@skills-mobility/ui`.

### 3. Subscription seam (design §5/§8)

- `src/hooks/useExecution(id)` and `useExecutionList({correlationId})` — a **polling**
  adapter behind a hook contract shaped so an SSE adapter can swap in later without
  touching callers.
- **Unit-test** the polling adapter against the hook contract: terminal-state stop and
  list reconciliation (design §8), so an SSE adapter reuses the same tests.

### 4. Three view levels (stubbed; all live now that #32 is merged)

- **Level 1 — list + correlation pivot** (FR-AU-16/17): `ExecutionSummary` table,
  newest first, with a correlation-id filter. Consumes `contracts.listExecutions` →
  `GET /executions` — **live on `main`**.
- **Level 2 — workflow detail** (FR-AU-19): header (status, correlation_id, timestamps),
  gate/decision panel from `gate_decision`, ordered step timeline from `steps`.
  Consumes `contracts.getExecution` → `GET /executions/{id}` — **fully live now**.
- **Level 3 — per-step master-detail**: select a step → an inline Radix
  `Collapsible` panel (docked in the workflow-detail layout, not a modal) →
  `@skills-mobility/ui` JSON viewer over `output`/`error`/status/timing.
- **Stub, don't invent:** per-step resolved `inputs` (FR-AU-18a / #28 G5) and the
  richer decision-artifact collection (FR-AU-18b / #28 G7) aren't in the API yet —
  render "not yet available" placeholders. **Exclude** the Orchestrator dev controls
  (`PUT /admin/plan-lookup-toggle`, `DELETE /admin/plans/{id}`) — the Admin UI never mutates.

## Verification

- `npm run build -w apps/admin` + root `npm run typecheck` clean.
- Run the Orchestrator on :8400, POST a few `/run-workflow` calls to seed executions,
  `npm run dev -w apps/admin`: **all three levels render real executions** — the list +
  correlation filter (`GET /executions`) and the detail/step views
  (`GET /executions/{id}`).
- `contracts` integration tests + hook-contract unit tests green. Branch off `main`
  directly (Plan 1 is already merged, so there is no branch left to stack on); don't
  push until asked. No AI attribution on commits.

## Status note

PR #32 (the `GET /executions` list endpoint) is **merged to `main`**, so nothing here
is gated on an in-flight branch. If you branch Plan 2 off `main` after pulling, the
level-1 endpoint is present.

## Progress Log

Implemented on `feat/admin-ui-scaffold` (branched off `main` at `a7ab5d7`, Plan 1's
PR #70 merge commit). Full check loop green:

- `npm run typecheck`: clean across `admin-ui`, `mock-lms-ui`, `@skills-mobility/contracts`,
  `@skills-mobility/ui`.
- `npm run test`: 34 tests passing — 10 in `apps/admin` (4 `useExecution`, 4
  `useExecutionList`, 2 `ExecutionListView`), 7 in `packages/contracts` (4 pre-existing
  + 3 new `orchestratorApi` tests: happy path, correlation-pivot query encoding,
  not-found), 17 in `packages/ui` (14 pre-existing + 3 new `EnvelopeModal` dialog tests:
  role/accessible-name, Escape-close, focus-restore).
- `npm run build -w apps/admin` and `-w apps/mock-lms`: both clean.
- `uv run pytest`: 108 passed (Python side untouched; one pre-existing, unrelated
  collection error in `services/learncard-wallet-adapter` confirmed present on `main`
  too — a local venv gap, not caused by this change).
- `uv run ruff check .`: 18 pre-existing findings, all in `.claude/skills/postgres/`,
  confirmed present on `main` — unrelated, out of scope.
- `uv run mypy libs/*/src services/*/src`: clean.
- Live smoke test via Playwright against a running Orchestrator (`:8400`) seeded with
  `/run-workflow` calls (a 3-execution correlation group + a 1-execution group) and
  `apps/mock-lms` (`:5173`/`:8000`): all three Admin UI levels render real data (list,
  correlation pivot — both the single-match auto-open and the multi-match scoped-list
  paths, workflow detail with a real 8-step timeline, inline step Collapsible with real
  `output` JSON); `EnvelopeModal`'s Radix Dialog fix (issue #71) verified live in
  `apps/mock-lms` — `role="dialog"`, Escape-to-close, focus lands in the dialog on
  open, backdrop-click-close, and focus restores to the exact triggering button on
  both Escape and backdrop-click.

### Review Notes

Internal-stabilize review (sub-agent, quick review over the full increment) found two
critical issues, both fixed before this pass closed:

1. **Keyboard bug in `ExecutionListView`'s row selection
   (`apps/admin/src/components/ExecutionListView.tsx`).** The original `<tr
   role="button" tabIndex={0} onKeyDown={...}>` pattern nested a real interactive
   control (the `CopyableId` copy button) inside the row's own keyboard-activation
   area: pressing Enter on the focused copy button bubbled a keydown up to the row,
   which called `preventDefault()` (suppressing the button's own click) and navigated
   to the workflow instead of copying. Overriding a `<tr>`'s implicit role to `button`
   also drops its native table-row semantics for screen readers navigating cell by
   cell. Fixed by removing the role/tabIndex/onKeyDown from the `<tr>` entirely (it
   keeps a plain mouse-only `onClick` as a "click anywhere in the row" convenience) and
   moving the actual keyboard-operable trigger to a real `<button className="row-open">`
   in the event-type cell, so there's exactly one interactive control per cell, no
   nested activation areas. Regression test added:
   `apps/admin/src/components/ExecutionListView.test.tsx`.
2. **No regression test for `EnvelopeModal`'s Radix Dialog upgrade
   (`packages/ui/src/EnvelopeModal.tsx`).** The dialog semantics, Escape-close, and
   focus-restore behavior — the actual point of the issue #71 fix — were only verified
   via a manual, uncommitted Playwright session. Added three tests to the existing
   `EnvelopeModal.test.tsx`: role/accessible-name, Escape-to-close, and focus-restore
   (the last one needed an `await new Promise(resolve => setTimeout(resolve, 0))` after
   `unmount()`, since Radix's `FocusScope` restores focus inside a real `setTimeout(…,
   0)`, not synchronously on unmount).

Two advisory items, left as-is for this plan:

3. **Unused `motion` dependency in `apps/admin/package.json`.** Copied from the
   `apps/mock-lms` scaffold template, but nothing under `apps/admin/src` imports from
   `motion`/`motion/react` yet. Removed — trivial to re-add (`npm install motion` at
   root) when a future expansion actually animates something in the Admin UI.
4. **`ExecutionListView`'s correlation-id pivot state doesn't survive a round trip
   through the detail view.** `correlationId`/`pivotInput` live in `ExecutionListView`,
   which fully unmounts the moment a workflow opens (single-match auto-navigate or a
   row click on a scoped list); clicking "Back to list" always lands on the full,
   unfiltered list rather than the scoped view the operator had before drilling in.
   Neither FR-AU-7 nor FR-AU-8 requires preserving it, and this is stub-quality scope
   for the initial scaffold — left as-is. Lifting `correlationId` up to `App` (or into
   the URL) would fix it if this becomes a real papercut later.
