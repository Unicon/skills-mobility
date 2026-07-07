# orchestrator — Orchestrator (Phase-1 plan executor)

The POC's **constrained plan executor** (design: [`docs/3_design/orchestrator.md`](../../docs/3_design/orchestrator.md),
requirements: [`docs/2_requirements/orchestrator.md`](../../docs/2_requirements/orchestrator.md),
ADR-0009/0011). It runs the two-stage hierarchical model: a **planner path**
(build context → pre-target gate → select targets → delivery-phase plan) then an
**executor path** (run the plan's steps one at a time, persisting each result).

In **Phase 1** the Workflow Actions / Delivery Targets seams are deterministic
stubs, and the Field Mapping / Field Synthesis / Translation Executor steps are
explicit no-ops — but they return the intended target-PoC artifact shapes so the
LLM services swap in later without reshaping the executor.

The components it calls live behind **injectable client seams** (`clients.py`);
Phase-1 defaults are in-process stubs, so the spine runs end to end with no
running services and no live LearnCard. The real Context Builder (#20, over
`/build-context`) and the #19 delivery services swap in at those seams.

## Layout

```
src/orchestrator/
  app.py       FastAPI factory: POST /run-workflow, GET /executions/{id},
               PUT /admin/plan-lookup-toggle, DELETE /admin/plans/{id}, /healthz
  config.py    settings (ORCHESTRATOR_PORT, ORCHESTRATOR_DB_PATH, ORCHESTRATOR_ISSUER_ID,
               LEARNCARD_DELIVERY_CONFIG_REF, *_URL seams, reusable_plan_lookup_enabled)
  engine.py    orchestration: planner path + executor path + execution-state persistence
  planner.py   pre-target gate, Delivery Targets stub, delivery-phase plan artifact
  executor.py  step loop: resolve input bindings, dispatch, persist each StepResult
  actions.py   action registry + Phase-1 action implementations (stubs/translation)
  obv3.py      minimal unsigned OBv3 builder (the issuer-side translation stub)
  clients.py   ContextBuilder / ProfileResolver / DeliveryRouter seams + Phase-1 stubs
  store.py     SQLite store: workflow_execution + workflow_step_execution + workflow_plan
  schemas.py   workflow-start, gate/plan artifacts, StepResult, ExecutionMetadata
```

## Trigger / inspect / admin

- `POST /run-workflow {execution_id, event_id, correlation_id, event}` — runs the
  plan and persists the trail; returns the `ExecutionMetadata`.
- `GET /executions/{id}` — the correlated execution metadata (status + per-step log + result).
- `PUT /admin/plan-lookup-toggle {enabled}` — turn reusable delivery-phase plan lookup on/off (FR-OR-28).
- `DELETE /admin/plans/{plan_id}` — drop a stored plan to force regeneration (FR-OR-29).

## What's stubbed (Phase 1)

- **Workflow Actions / Delivery Targets** → deterministic gate (`continue`) + fixed target set.
- **Field Mapping / Field Synthesis** → contract-shaped stubs (return the #27 §10 response envelope / synthesized-values map; the plan supplies `transformation_type`, `delivery_target`, and `synthesis_allowed` as independent literals; no real artifacts yet); **Translation Executor** → the OBv3/wallet-payload builders.
- **Profile Resolver / Delivery Router (+ LearnCard adapters)** → canned profile/DID + signed VC + accepted delivery. Set `ORCHESTRATOR_PROFILE_RESOLVER_URL` (#51) and/or `ORCHESTRATOR_DELIVERY_ROUTER_URL` (#56) to call the real services over HTTP instead.

## Run / test

```bash
uv sync --all-packages            # install workspace members (required before first run)
uv run orchestrator               # serves on :8400 — interactive docs at http://127.0.0.1:8400/docs
uv run pytest services/orchestrator
uv run ruff check services/orchestrator
uv run mypy services/orchestrator/src
```

Port is `8400` by default (8300 is Consul's RPC port and conflicts); override with `ORCHESTRATOR_PORT`.

## Manual testing (end-to-end shape)

The Orchestrator is triggered by the Event Consumer, but you can drive it directly:

1. Run the Mock LMS — `uv run mock-lms` (:8000) — and trigger an event from its UI
   (or `POST /demo/courses/{id}/actions`); copy the emitted event envelope from the response.
2. Build the `/run-workflow` body by combining that envelope with made-up ids:
   ```bash
   curl -X PUT localhost:8400/admin/plan-lookup-toggle -H 'content-type: application/json' -d '{"enabled": false}'
   curl -X POST localhost:8400/run-workflow -H 'content-type: application/json' -d '{
     "execution_id": "wf_1", "event_id": "evt_1", "correlation_id": "corr_1",
     "event": { ... the copied envelope ... }
   }'
   ```
   (With the Context Builder running and `ORCHESTRATOR_CONTEXT_BUILDER_URL` set, the
   real `/build-context` is called; otherwise the in-process stub bundle is used. The
   same applies to `ORCHESTRATOR_PROFILE_RESOLVER_URL` and `ORCHESTRATOR_DELIVERY_ROUTER_URL`
   for real LearnCard profile resolution and issuance/delivery.)
3. Read it back: `GET localhost:8400/executions/wf_1` — status, per-step log, result.
