# transformation-executor

The deterministic execution layer that applies LLM-produced JSONata mapping
expressions to assembled source payloads and synthesized values. It takes one
already-validated mapping artifact, evaluates it against the supplied data, and
returns a normalized result — always HTTP 200, `status: "succeeded"` or
`status: "failed"`.  The Transformation Executor is **not** an orchestrator and
**not** a transformation designer; it only runs what the Field Mapping service
produced and the Orchestrator approved. See the architectural contract in AGENTS.md:
LLM output never flows straight to delivery — this service is the deterministic
step between the two.

## Setup

```bash
uv sync --all-packages
cp services/transformation-executor/.env.example services/transformation-executor/.env
```

## Run

```bash
uv run transformation-executor   # http://localhost:8160 — Swagger at /docs
```

Swagger UI: `http://localhost:8160/docs`

## Smoke test

```bash
curl -s -X POST http://localhost:8160/execute \
  -H 'Content-Type: application/json' \
  -d '{"execution_id": "test-1", "transformation_type": "learncard", "mapping": "{ \"name\": source_payloads.lms.name }", "source_payloads": {"lms": {"name": "Alice"}}}'
```

Expected response: `{"status":"succeeded","transformation_type":"learncard","result":{"name":"Alice"},"error":null}`

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `TRANSFORMATION_EXECUTOR_PORT` | `8160` | Local HTTP port |
| `TRANSFORMATION_EXECUTOR_LOG_LEVEL` | `INFO` | Root log level |

## Test

```bash
uv run pytest services/transformation-executor
```
