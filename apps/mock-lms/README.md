# mock-lms-ui — Mock LMS demo console

Presenter-facing SPA for the Skills Mobility POC: a three-pane console to
inspect the mock LMS source data, trigger credential events, and watch them
stream onto the bus in real time. Pairs with the `services/mock-lms` backend.

React + TypeScript + Vite. Deployed as a static SPA (S3 + CloudFront per
ADR-0002); auth is CloudFront-layer (the UI sends the role as `X-Demo-Role`).

## Panes

- **Scenario rail** — list the canonical scenarios; `Emit` runs one (publishes its events), `Reset` clears the emission log.
- **Inspector** — browses the active scenario's Canvas-style source data (course, outcome/skill, assignments, submissions) via `/api/v1/*` — the same surface the Context Builder reads.
- **Emission timeline** — live SSE feed (`/demo/stream`); color-coded by event type, newest highlighted, click any event for the raw envelope JSON, copyable correlation ids.

## Develop

Run the backend first (defaults to `:8000`), then the UI dev server — Vite
proxies `/api`, `/demo`, and `/healthz` to the backend, so the SPA is
same-origin and SSE streams cleanly.

```bash
# terminal 1 — backend (from repo root)
uv run mock-lms                  # http://127.0.0.1:8000

# terminal 2 — UI
cd apps/mock-lms
npm install
npm run dev                      # http://localhost:5173
```

## Build / check

```bash
npm run build        # tsc --noEmit + vite build -> dist/
npm run typecheck
```

Design: dark "mission-control" instrumentation aesthetic — gold credential
signal, live-green status, per-event telemetry colors, Archivo + JetBrains Mono.
