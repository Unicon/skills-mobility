# mock-lms — Mock Event Producer / Mock LMS

Source-system service for the Skills Mobility POC. It does two jobs:

1. **Serves Canvas-style metadata APIs** (`/api/v1/...`) over a fixed, seeded
   catalog — the "LMS Metadata APIs" the Context Builder reads.
2. **Emits credential events** (`/demo/...`) in the Canvas Live Events envelope
   onto the bus, driven by single triggers or repeatable scenarios.

See the requirements and design docs:
[requirements](../../docs/2_requirements/mock-event-producer.md) ·
[design](../../docs/3_design/mock-event-producer.md).

## Layout

```
src/mock_lms/
  app.py            FastAPI factory + /healthz
  config.py         settings (MOCK_LMS_* env)
  auth.py           CloudFront-layer role dependency (ADR-0002)
  scenarios.py      Canvas-style entities, in-memory store, fixture loader
  builders.py       trigger + scenario data -> Live Event envelope
  emission.py       Emitter (Local/EventBridge) + bounded EmissionLog
  api/metadata.py   Canvas-style read endpoints
  api/emit.py       /demo emit, run-scenario, reset, emissions log
  fixtures/         version-controlled catalog + canonical scenarios
```

## Run (from repo root)

```bash
uv sync --all-packages
uv run mock-lms                 # serves on http://127.0.0.1:8000
# OpenAPI docs at /docs
```

### Try it

```bash
# Inspect seeded data the Context Builder would read
curl localhost:8000/api/v1/courses/1001
curl 'localhost:8000/api/v1/courses/1001/outcome_results?user_ids[]=2001&outcome_ids[]=3001&include[]=alignments'

# List and run a canonical scenario (emits an event, returns the envelope + correlation id)
curl localhost:8000/demo/scenarios
curl -X POST localhost:8000/demo/scenarios/skill-mastered/run

# Read the emission log (backs the UI live feed)
curl localhost:8000/demo/emissions
```

## Data & repeatability

Mock data follows a **generate → capture → commit → replay** model:

1. **Generate** — a seeded Faker generator (`generators/`) builds a realistic
   `Catalog` + `Scenario` set. Entity ids are deterministic sequences
   (course `1001..`, learner `2001..`, outcome `3001..`, assignment `4001..`);
   content (names, titles, dates, grades) is Faker-driven and seeded. The
   primary learner+course is guaranteed a happy path (mastered outcome result +
   graded submission), so the canonical scenarios always demonstrate mastery.
2. **Capture** — the CLI serializes that output to the committed
   `fixtures/catalog.json` + `fixtures/scenarios.json` (the canonical snapshot).
3. **Replay** — at runtime the service loads the frozen snapshot read-only; it
   **never runs the generator**. So API determinism doesn't depend on the
   generator being deterministic — it depends on the file being frozen.

```bash
uv run mock-lms-generate                       # rewrite committed fixtures (seed 42, 1 learner, 1 course)
uv run mock-lms-generate --learners 5 --courses 2 --out-dir generated-fixtures
MOCK_LMS_FIXTURES_DIR=generated-fixtures uv run mock-lms   # serve a generated set
```

`generated-fixtures/` is gitignored scratch space; the committed `fixtures/` are
the canonical demo data. Same seed → byte-identical fixtures (guarded by
`tests/test_generators.py`).

**Two kinds of repeatability:** (a) *source data* is identical every run
(frozen snapshot → deterministic metadata APIs); (b) *emitted events* get fresh
`event_id`/`correlation_id` per run over stable business keys, so a scenario
re-runs cleanly all demo long while staying traceable.

## Test / lint

```bash
uv run pytest services/mock-lms
uv run ruff check services/mock-lms
uv run mypy services/mock-lms/src
```

## Status

Implements design build-order steps 1–4: event contracts, Canvas-style metadata
APIs, emitter, emission API, canonical scenarios, and the SSE live feed
(`GET /demo/stream`). The demo UI (`apps/mock-lms`, step 5) consumes this
service. Not yet built: the wired `EventBridgeEmitter` + CDK infra (step 6) and
the CloudFront-layer auth deploy (step 7).
