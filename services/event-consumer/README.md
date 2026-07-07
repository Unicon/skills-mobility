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
  config.py     settings (EVENT_CONSUMER_DB_PATH, EVENT_CONSUMER_ORCHESTRATOR_URL)
  identity.py   envelope validation (FR-EC-9) + idempotency key derivation (FR-EC-11)
  store.py      SQLite store: ingress_idempotency + workflow_execution + orchestrator_outbox
  consumer.py   ingress logic: validate → claim identity → create execution → hand off
  handoff.py    Orchestrator handoff seam: CaptureHandoff (local) / HttpHandoff (POST /run-workflow)
```

Configuration via env (see [`.env.example`](./.env.example)): `EVENT_CONSUMER_DB_PATH`,
`EVENT_CONSUMER_ORCHESTRATOR_URL` (set to forward handoffs to the real Orchestrator;
unset = capture mode), and `EVENT_CONSUMER_LOG_LEVEL` (default `INFO`; set `WARNING`
to quiet the ingress logs or `DEBUG` for more). The entrypoint calls
`logging.basicConfig()` at that level so the ingress logs are actually emitted.

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
uv sync --all-packages           # install workspace members (required before first run)
uv run event-consumer            # serves on :8200 — interactive docs at http://127.0.0.1:8200/docs
uv run pytest services/event-consumer
uv run ruff check services/event-consumer
uv run mypy services/event-consumer/src
```

## Manual smoke test (end-to-end)

Confirms the Mock LMS → Event Consumer integration and the ingress decision (design §7):

```bash
# 1. Start the Event Consumer (terminal 1)
uv sync --all-packages
uv run event-consumer                                          # :8200

# 2. Start the Mock LMS pointed at it (terminal 2)
MOCK_LMS_EVENT_CONSUMER_URL=http://127.0.0.1:8200 uv run mock-lms   # :8000
```

Trigger an event from the Mock LMS UI (or `POST /demo/courses/{id}/actions`), then
inspect the result:

- **Logs** — the Event Consumer logs event receipt, the idempotency decision, and
  the new execution id (`ingest created: execution_id=… status=handoff_captured`).
- **Swagger** — POST envelopes manually at `http://127.0.0.1:8200/docs`.
- **SQLite** — confirm the event landed:

  ```bash
  sqlite3 event-consumer.db "SELECT execution_id, event_type, status FROM workflow_execution;"
  sqlite3 event-consumer.db "SELECT execution_id FROM orchestrator_outbox;"   # capture mode
  ```

Re-running the same scenario? `POST /reset` (or the Mock LMS Reset) clears state first.
