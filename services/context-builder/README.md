# context-builder — Context Builder

Deterministic source-data aggregation for the Orchestrator (Skills Mobility POC).
Given an event, it selects a **fetch profile**, runs the profile's ordered LMS
Resource API calls (with id-chaining), and returns a single JSON **context
bundle**. It makes no decisions and runs no LLM — endpoint selection is fixed
configuration.

See the design: [`docs/3_design/context-builder.md`](../../docs/3_design/context-builder.md)
and requirements [`docs/2_requirements/context-builder.md`](../../docs/2_requirements/context-builder.md).

## Layout

```
src/context_builder/
  app.py             FastAPI factory + POST /internal/build-context + /healthz
  config.py          settings (CONTEXT_BUILDER_LMS_BASE_URL)
  builder.py         event → profile selection → bundle / failure assembly
  engine.py          fetch-profile execution (param resolution, condition, select, for_each)
  profiles.py        FetchProfile model + YAML loader
  lms_client.py      LMSClient protocol + httpx implementation
  schemas.py         request / bundle / failure contracts
  fetch_profiles/    versioned YAML recipes (skill_mastered, course_completed, badge_awarded)
```

## Run (from repo root)

```bash
uv sync --all-packages
CONTEXT_BUILDER_LMS_BASE_URL=http://127.0.0.1:8000 uv run context-builder   # serves on :8100
```

It reads the Mock LMS Resource APIs, so run `uv run mock-lms` (:8000) alongside it.

```bash
# Build a context bundle for an event envelope
curl -X POST localhost:8100/internal/build-context -H 'content-type: application/json' \
  -d '{"execution_id":"wf_1","event":{ ... emitted envelope ... }}'
```

## Fetch profiles

One YAML profile per event type in `fetch_profiles/` (the Source Fetch Rules
Store). Each step has an `output_key`, an `endpoint` with `{param}` placeholders,
and `params` sourced from the event, a prior step's response, or a `for_each`
item. Steps may carry a `condition` (run only if a prior field is present/absent),
a `select` (store one matching element of a list response), or a `for_each`
(run once per matching item). A failed LMS call is stored as `{"error": {...}}`
under its key; the bundle is always returned unless the profile can't start
(unknown event type / missing required identifier → a distinct failure response).

## Test / lint / types

```bash
uv run pytest services/context-builder
uv run ruff check services/context-builder
uv run mypy services/context-builder/src
```
