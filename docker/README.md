# Local docker-compose environment

Brings up the Phase-1 spine as containers so you can build + run the whole
pipeline locally with one command. (Asked for by Mary; scoped "spine now, grow as
the delivery PRs merge.")

```bash
docker compose up --build     # from the repo root
```

Then: mock-lms `http://localhost:8000`, context-builder `:8100`,
event-consumer `:8200`, orchestrator `:8400` (each serves `/healthz`).

## How it's wired

```
mock-lms (8000) --emits--> event-consumer (8200) --hands off--> orchestrator (8400)
     ^                                                                  |
     |                                                          builds context
     +------------------ context-builder (8100) <----------------------+
```

Set via compose env (services reach each other by service name):

| Service | Env | Points at |
| --- | --- | --- |
| mock-lms | `MOCK_LMS_EVENT_CONSUMER_URL` | `http://event-consumer:8200` |
| event-consumer | `EVENT_CONSUMER_ORCHESTRATOR_URL` | `http://orchestrator:8400` |
| orchestrator | `ORCHESTRATOR_CONTEXT_BUILDER_URL` | `http://context-builder:8100` |
| context-builder | `CONTEXT_BUILDER_LMS_BASE_URL` | `http://mock-lms:8000` |

SQLite state for event-consumer + orchestrator lives in named volumes.

## The image pattern

One shared image (`Dockerfile.python`) builds the whole uv workspace
(`uv sync --all-packages --frozen`); each service is the *same* image run with a
different `command`. The commands run `uvicorn` on `0.0.0.0` (the `run()`
entrypoints bind `127.0.0.1` — right for local dev, unreachable across
containers) and call `logging.basicConfig(INFO)` first, so the services' own
app-level logs (gate decisions, ingress, LMS fetches) show in `docker compose
logs`, not just uvicorn's access lines.

## Adding a service as its PR merges

1. Add a service block to `docker-compose.yml` (copy an existing one, set the
   `command` module + port + env).
2. Wire the orchestrator's delivery envs when the delivery layer lands:
   `ORCHESTRATOR_PROFILE_RESOLVER_URL`, `ORCHESTRATOR_DELIVERY_ROUTER_URL`, and the
   router's `DELIVERY_ROUTER_LEARNCARD_{ISSUER,WALLET}_URL`.
3. The **LearnCard Issuer Adapter** is Node/TS — it needs a separate
   `docker/Dockerfile.node`, and its `SECURE_SEED` + the wallet/resolver
   `LEARNCARD_*` tokens come from `tools/learncard-demo` (ADR-0020), supplied via
   a gitignored `.env` / compose `env_file`.

## Not included

The mock-lms React UI runs separately (`cd apps/mock-lms && npm run dev`) — this
compose is the backend pipeline.
