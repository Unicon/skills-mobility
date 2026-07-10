# admin-ui — Admin UI

Read-only observability SPA for the Skills Mobility POC. Downstream pair of the
**Mock LMS UI**: a presenter triggers a workflow there, copies the run's
`correlation_id`, and follows that same workflow here — seeing how the
Orchestrator planned and executed it. Pairs with the `services/orchestrator`
backend.

Triggering Actions, browsing course data, and the emission feed are the
**Mock LMS UI**'s job — a separate app, out of scope here (requirements §8, ADR-0002).

React + TypeScript + Vite. Deployed as a static SPA (S3 + CloudFront per
ADR-0002); auth is CloudFront-layer, a single demo user. The Admin UI never
mutates — it only reads the Orchestrator's execution store.

## Views

- **Workflow list** — recent executions (correlation id, event type, status,
  step progress), newest first. A correlation-id pivot at the top resolves a
  pasted id to its correlation group: one match opens the workflow directly,
  several scope the list to the group, none shows an empty state.
- **Workflow detail** — header (ids, event type, plan id, final outcome), the
  recorded gate decision, and the ordered step timeline.
- **Step detail** — selecting a step expands an inline panel (master-detail,
  not a separate page) with its resolved output, error, attempt, and timing as
  raw JSON via the shared viewer.

## Develop

Run the backend first (defaults to `:8400`), then the UI dev server — Vite
proxies `/executions` and `/healthz` to the backend, so the SPA is
same-origin.

```bash
# terminal 1 — backend (from repo root)
uv run orchestrator               # http://127.0.0.1:8400

# terminal 2 — UI (npm workspace, ADR-0020) — install once from the repo root
npm install
npm run dev -w apps/admin         # http://localhost:5174
```

The Orchestrator has no executions until something runs a workflow. Two ways
to get one:

**Seed it directly** — quickest, no other services needed:

```bash
curl -X POST localhost:8400/run-workflow -H 'content-type: application/json' -d '{
  "execution_id": "wf_1", "correlation_id": "corr_1",
  "event": {"metadata": {"event_name": "learning_outcome_result_created"}, "body": {}}
}'
```

**Trigger it from the Mock LMS UI** — the real demo path, but the Mock LMS does
**not** call the Orchestrator directly. It emits to the **Event Consumer**
(`services/event-consumer`), which mints the execution and hands off to the
Orchestrator — both hops are opt-in via env vars, so all three backends need
to be started with the chain wired:

```bash
# terminal 1
uv run orchestrator                                                        # :8400

# terminal 2 — ORCHESTRATOR_URL points this hop at the Orchestrator
EVENT_CONSUMER_ORCHESTRATOR_URL=http://127.0.0.1:8400 uv run event-consumer # :8200

# terminal 3 — EVENT_CONSUMER_URL points Mock LMS at the Event Consumer
MOCK_LMS_EVENT_CONSUMER_URL=http://127.0.0.1:8200 uv run mock-lms          # :8000
```

Then `npm run dev -w apps/mock-lms`, trigger an Action, copy its
`correlation_id`, and paste it into the Admin UI's pivot. See
[`services/event-consumer/README.md`](../../services/event-consumer/README.md)
for the ingress details.

## Build / check

```bash
npm run build -w apps/admin       # tsc --noEmit + vite build -> dist/
npm run typecheck -w apps/admin
npm run test -w apps/admin
```

Depends on the shared `@skills-mobility/ui` and `@skills-mobility/contracts`
workspace packages (`packages/ui`, `packages/contracts`) for design tokens,
shared primitives, and the Orchestrator read client/types.

Design: re-expresses the Mock LMS's dark "mission-control" aesthetic through
the shared token layer (NFR-AU-4) — same gold/live-green/telemetry-color
identity, applied to a workflow timeline instead of a course console.
