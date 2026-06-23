# event-consumer — Event Consumer

The POC's **workflow ingress boundary** (#16 / ADR-0014 / ADR-0015). It receives
an event, validates the envelope, enforces event-level **idempotency**, creates
the initial workflow execution record, and hands the run to the Orchestrator.
It is intentionally thin — no context-building, planning, policy, or delivery.

See [`docs/3_design/event-consumer.md`](../../docs/3_design/event-consumer.md)
and [`docs/2_requirements/event-consumer.md`](../../docs/2_requirements/event-consumer.md).

## Layout

```
src/event_consumer/
  app.py        FastAPI factory + POST /ingest, POST /reset, /healthz
  config.py     settings (EVENT_CONSUMER_DB_PATH)
  identity.py   envelope validation (FR-EC-9) + idempotency key derivation (FR-EC-11)
  store.py      SQLite store: ingress_idempotency + workflow_execution + orchestrator_outbox
  consumer.py   ingress logic: validate → claim identity → create execution → capture handoff
```

## Ingress contract

`POST /ingest` takes the raw event envelope and returns the ingress decision:

- **created** (`200`) — new event; an execution id + initial `workflow_execution`
  record are created and the Orchestrator handoff is captured.
- **duplicate** (`200`) — the event's business identity (`event_name` + `user_id`
  + the event-type object id) was already seen; no new workflow is created.
- **rejected** (`422`) — the envelope failed validation; a `rejected` record is
  written and the event is acked (not retried).

`POST /reset` clears the idempotency + execution + outbox state so a demo can
re-run the same scenario (FR-EC-23) — the Mock LMS Reset calls this.

## Local vs AWS

Locally this is a FastAPI service over SQLite; `POST /ingest` stands in for the
EventBridge → Lambda trigger, and the Orchestrator handoff is **captured** in the
`orchestrator_outbox` table until the Orchestrator exists (ADR-0015). The same
logical store split maps to DynamoDB tables in AWS.

## Run / test

```bash
uv run event-consumer            # serves on :8200
uv run pytest services/event-consumer
uv run ruff check services/event-consumer
uv run mypy services/event-consumer/src
```
