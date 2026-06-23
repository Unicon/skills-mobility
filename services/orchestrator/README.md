# orchestrator — Orchestrator (Phase-1 stub)

Executes the validated workflow plan. In **Phase 1** the plan is a fixed
deterministic sequence (no LLM planning, per [phase-1-poc-slice.md](../../docs/2_requirements/phase-1-poc-slice.md)):
build context → resolve LearnCard profile → prepare + issue an OBv3 credential →
deliver to wallet → record the outcome. The LLM Decision Services and Policy
Rules are **bypassed**; `prepare_issuer_input` is the Orchestrator's deterministic
stand-in for the transformation pipeline.

The components it calls live behind **injectable client seams** (`clients.py`).
The Phase-1 defaults are in-process **stubs**, so the spine runs end to end with
no running services and no live LearnCard. Real HTTP clients swap in when the
Context Builder (#20) and the #19 delivery services are wired.

## Layout

```
src/orchestrator/
  app.py       FastAPI factory + POST /run-workflow, GET /executions/{id}, /healthz
  config.py    settings (ORCHESTRATOR_DB_PATH, ORCHESTRATOR_ISSUER_ID)
  runner.py    the Phase-1 deterministic plan (pure; returns the ExecutionRecord)
  obv3.py      minimal unsigned OBv3 builder + wallet-input prep (the transform stub)
  clients.py   ContextBuilder / ProfileResolver / DeliveryRouter seams + Phase-1 stubs
  store.py     SQLite execution-log store (the correlated record the Admin UI will read)
  schemas.py   RunRequest + ExecutionRecord / StepTrace
```

## Trigger

`POST /run-workflow {execution_id, event}` runs the plan and persists the trace;
`GET /executions/{id}` returns the recorded `ExecutionRecord` (status + per-step
trace + result). Wiring the Event Consumer's handoff (capture-mode today) to POST
here is a follow-up.

## What's stubbed (Phase 1)

- **Profile Resolver** → canned `profileId`/DID.
- **Delivery Router + LearnCard Issuer/Wallet adapters** → canned "signed" VC + accepted delivery.
- **Context Builder** seam defaults to a canned bundle; the real CB (#20) is the swap-in.

## Run / test

```bash
uv run orchestrator               # serves on :8300
uv run pytest services/orchestrator
uv run ruff check services/orchestrator
uv run mypy services/orchestrator/src
```
