# mock-lms-ui — Mock LMS demo console

Presenter-facing SPA for the Skills Mobility POC. A course-centric console that
**mimics an LMS**: browse a course's source data, trigger a grading Action, and
see the event it emits — so a stakeholder can compare the source data to the
badge issued downstream. Pairs with the `services/mock-lms` backend.

Observing the orchestration itself (live execution timeline, per-step status,
correlation tracing) is the **Admin UI's** job — a separate app, out of scope
here (design §4, ADR-0002).

React + TypeScript + Vite. Deployed as a static SPA (S3 + CloudFront per
ADR-0002); auth is CloudFront-layer, a single demo user.

## Panes

- **Courses** — pick a course (standard or digital-credential); shows kind, institution, term, and how many Actions it offers.
- **Inspector** — browses the course's Canvas-style source data (modules, assignments, the selected learner's submissions, rubrics) via `/api/v1/*` — the same surface the Context Builder reads.
- **Trigger & Confirm** — choose scope (one learner / all) and run a grading Action; the emitted envelope(s) and the run's `correlation_id` come back synchronously, click an event for the raw envelope JSON.

## Develop

Run the backend first (defaults to `:8000`), then the UI dev server — Vite
proxies `/api`, `/demo`, and `/healthz` to the backend, so the SPA is
same-origin.

```bash
# terminal 1 — backend (from repo root)
uv run mock-lms                  # http://127.0.0.1:8000

# terminal 2 — UI (npm workspace, ADR-0020) — install once from the repo root
npm install
npm run dev -w apps/mock-lms     # http://localhost:5173
```

## Build / check

```bash
npm run build -w apps/mock-lms       # tsc --noEmit + vite build -> dist/
npm run typecheck -w apps/mock-lms
```

Depends on the shared `@skills-mobility/ui` and `@skills-mobility/contracts`
workspace packages (`packages/ui`, `packages/contracts`) for design tokens,
shared primitives, and the API client/types.

Design: dark "mission-control" instrumentation aesthetic — gold credential
signal, live-green status, per-event telemetry colors, Archivo + JetBrains Mono.
