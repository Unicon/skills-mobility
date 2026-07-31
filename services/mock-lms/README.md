# mock-lms — Mock LMS (Event Producer + LMS Resource APIs)

Source-system service for the Skills Mobility POC. It does two jobs:

1. **Serves Canvas-style LMS Resource APIs** (`/api/v1/...`) over a fixed, seeded
   catalog — the read surface the Context Builder (and the demo UI) consume.
2. **Emits credential events** (`/demo/...`) in the Canvas Live Events envelope
   onto the bus, driven by course **Actions** (grade an assignment).

See the requirements and design docs:
[event producer](../../docs/2_requirements/mock-lms-event-producer.md) ·
[APIs](../../docs/2_requirements/mock-lms-apis.md) ·
[UI](../../docs/2_requirements/mock-lms-ui.md) ·
[design](../../docs/3_design/mock-lms.md).

## Layout

```
src/mock_lms/
  app.py            FastAPI factory + /healthz
  config.py         settings (MOCK_LMS_* env)
  catalog.py        entity models, in-memory read-only store, fixture loader
  events.py         Action + catalog data -> Live Event envelope
  emitter.py        Emitter: LocalEmitter (dev) / EventBridgeEmitter (AWS)
  api/resources.py  Canvas-style read endpoints (/api/v1)
  api/emit.py       /demo Action emit, reset, course list
  generators/       seeded catalog generator (authoring tool; not in the runtime path)
  fixtures/         committed, canonical catalog.json (loaded at runtime)
```

## Run (from repo root)

```bash
uv sync --all-packages
uv run mock-lms                 # serves on http://127.0.0.1:8000

# Forward emitted events to a running Event Consumer (unset = events are
# emitted locally only; see .env.example for the full MOCK_LMS_* set):
MOCK_LMS_EVENT_CONSUMER_URL=http://127.0.0.1:8200 uv run mock-lms
```

OpenAPI docs are at `/docs`. The committed `fixtures/catalog.json` loads
automatically — running the service needs no extra setup.

### Try it

The catalog ships committed, so these work against a freshly started service.
Course ids are the Canvas course codes from the roster (e.g. `ACCY-111`), not
integers. List the courses and their Actions first, then drill in:

```bash
curl localhost:8000/demo/courses
```

```bash
# Inspect seeded data the Context Builder would read (use a real course id)
curl localhost:8000/api/v1/courses/ACCY-111
curl localhost:8000/api/v1/courses/ACCY-111/assignments
curl localhost:8000/api/v1/courses/ACCY-111/students/submissions
```

```bash
# Run an Action: grades an assignment and emits the event, returning the
# envelope(s) + correlation id. grade-m1 is the competency (happy) skill-mastery
# variant; grade-m2 is the sub-competency (edge) variant.
curl -X POST localhost:8000/demo/courses/ACCY-111/actions \
  -H 'content-type: application/json' \
  -d '{"action_id": "ACCY-111-grade-m1", "scope": "one"}'

curl -X POST localhost:8000/demo/reset    # clean re-run: clears emission state and cascades
                                          # the reset to the Event Consumer -> Orchestrator
```

## Data & repeatability

Mock data follows a **generate → capture → commit → replay** model:

1. **Generate** — a seeded Faker generator (`generators/`) assembles the
   `Catalog` from a small subset of the PM's Canvas SIS-style roster CSVs plus a
   generated academic/credential layer (modules, outcomes, assignments,
   submissions, rubrics, badges). Ids are derived from stable business keys and
   the date window is fixed, so a given seed + roster + Faker version yields
   byte-identical output.
2. **Capture** — the CLI serializes that output to the committed
   `fixtures/catalog.json` (the canonical snapshot).
3. **Replay** — at runtime the service loads the frozen snapshot read-only and
   **never runs the generator**. API determinism depends on the file being
   frozen, not on the generator.

### Regenerating the fixture

The generator reads the roster CSVs (`course_sections.csv`, `users.csv`,
`enrollments.csv`) from `--csv-dir` (default: the **gitignored**
`services/mock-lms/seed-data/`). Those CSVs are input artifacts kept out of the
repo — drop them into `services/mock-lms/seed-data/` first (only needed to
regenerate; not to run the service).

```bash
uv run mock-lms-generate                                  # rewrite committed fixture (seed 42)
uv run mock-lms-generate --courses 20 --learners-per-course 30 \
  --out-dir generated-fixtures                            # a larger set, off to the side
MOCK_LMS_FIXTURES_DIR=generated-fixtures uv run mock-lms  # serve that set instead
```

Flags:

- `--seed` — deterministic seed (default 42).
- `--courses` — max courses to pull, split ~2:1 standard:digital-credential with
  at least one of each (default 6; capped by the roster).
- `--learners-per-course` — max enrolled learners per course (default 6; capped
  by the section's enrollment).
- `--csv-dir` — roster CSV directory (default `services/mock-lms/seed-data/`).
- `--out-dir` — where to write `catalog.json` (default: committed `fixtures/`).

`generated-fixtures/` is gitignored scratch space; the committed `fixtures/` is
the canonical demo data. The seed always carries **both course kinds** and
**both variants of each event** — competency vs sub-competency (`1.0.0` /
`1.2.0` outcome titles), passing vs failing final grade, accepted vs unaccepted
badge — so the happy and edge paths are both demonstrable.

## Test / lint / types

```bash
uv run pytest services/mock-lms
uv run ruff check services/mock-lms
uv run mypy services/mock-lms/src
```

## Status

Implements design build-order steps 1–4: event contracts (`libs/events`),
Canvas-style LMS Resource APIs, the emitter, and the Action emission API over a
seeded catalog. The demo UI (`apps/mock-lms`, step 5) consumes this service. Not
yet built: the wired `EventBridgeEmitter` + CDK infra (step 6) and the
CloudFront-layer auth deploy (step 7).
