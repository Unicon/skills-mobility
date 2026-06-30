# Pre-PR Checklist — Code PRs

Run this before opening a **code** PR (a new/changed `services/*` or `apps/*` module). It captures the standards that have come up repeatedly in review, so we address them up front instead of in a re-review round. It complements the task-completion checklist in [`AGENTS.md`](../AGENTS.md) (tests pass, lint/types clean, no secrets, no AI attribution) — this doc is the service/PR-shaped layer on top.

Most of these are derived from recurring review feedback on the first wave of services (#4 Mock LMS, #20 Context Builder, #21 Event Consumer, #22 Orchestrator). PR references are cited so the rationale is traceable.

## Quick checklist

```
Service scaffolding (new or changed service)
[ ] logging.basicConfig() in run() + a configurable <SERVICE>_LOG_LEVEL (default INFO)
[ ] logger.info() at the key transitions (not just a silent DB write)
[ ] README: `uv sync --all-packages` as the first run step
[ ] README: Swagger /docs link with the concrete port
[ ] README: a manual end-to-end / smoke-test section
[ ] .env.example covering every new env var
[ ] Port configurable via <SERVICE>_PORT; default in the 84xx range (NOT 8300 — Consul)

Code & API
[ ] Closed value sets are Literal/StrEnum, not str (turn the documenting comment into the type)
[ ] HTTP clients call resp.raise_for_status() — never swallow a non-2xx
[ ] No silent drops: surface or at least document discarded items; advance status fields through their documented states
[ ] Names reflect the concept; REST verb/path matches the action (a toggle is a PUT, not a POST that "creates")
[ ] Hard-coded "magic" values are configurable (env/CLI) and documented in the README
[ ] Non-obvious models / branches carry a one-line docstring or comment

Tests
[ ] The primary endpoint is tested at the HTTP layer (happy path + a malformed/422), not just /healthz
[ ] Assertions check REAL data on every output key — not presence-only against empty stubs
[ ] Tricky pure helpers have direct unit tests (edge cases), not just indirect integration coverage
[ ] Tests assert the behavioral consequence of a flag/branch, not just that the toggle flips

Docs & spec alignment
[ ] Design docs match the implementation (endpoint paths, field names, examples, CLI flags)
[ ] The exact API-contract details from the design doc are honored (query params, required fields)
[ ] ADR edits follow the lifecycle convention (ADR-0019): reversals stay visible (Status + Supersedes)

Project-specific
[ ] Mock data/events do NOT bake in answers the LLM Decision Services are meant to discern
[ ] Future-service seams are present even when Phase-1-stubbed (input bindings, no-op steps)
[ ] New libs ship a py.typed marker (force-included in the wheel) so consumers' mypy passes
```

## Notes (the why)

### Service scaffolding
- **Logging** — every service needs `logging.basicConfig(level=settings.log_level.upper())` in `run()` (uvicorn doesn't configure app loggers, so `logger.info()` calls are silently dropped without it) plus a `<SERVICE>_LOG_LEVEL` setting. Log the audit-relevant transitions: ingress decision, gate decision, plan reuse-vs-generate, per-step execution, fetch attempts. *(#20 FR-CB15, #21, #22 — context-builder is the reference pattern.)*
- **README** — `uv sync --all-packages` first (the service isn't importable as a workspace member until installed); the Swagger `/docs` URL with the real port; a manual smoke-test section that actually works end to end (order the steps so they don't 404). *(#4, #20, #21, #22.)*
- **`.env.example`** — accompany any new env var with an example entry. *(#21.)*
- **Port** — configurable via `<SERVICE>_PORT`; **avoid 8300** (Consul's default RPC port, conflicts under Docker Desktop). Current allocation: Mock LMS 8000, Context Builder 8100, Event Consumer 8200, Orchestrator 8400. *(#22.)*

### Code & API
- **Enums over `str`** — if a field has a closed value set already written in a comment, make it a `Literal`/`StrEnum`. *(#22.)*
- **Surface failures** — HTTP clients call `raise_for_status()`; don't silently drop items (document the intent if a drop is deliberate); status fields should advance through their documented states (`created → handoff_sent`, etc.) so the record is informative. *(#20, #21.)*
- **Naming & REST semantics** — names should reflect the concept (`ExecutionMetadata`, not `ExecutionView`); the HTTP verb/path should match the action (toggling a setting is `PUT /…-toggle`, not `POST`). *(#22.)*
- **Configurable, not hard-coded** — counts/splits/limits go in env or CLI params and are documented. *(#4.)*

### Tests
- **Primary endpoint + real data** — test the endpoint that matters at the HTTP layer (happy + malformed), and assert actual values on every output key rather than presence against `(200, [])` stubs. *(#20.)*
- **Unit-test the tricky bits** — pure helpers with edge cases (path-walking, branching, plan lookup) get direct unit tests, and tests should prove the behavioral consequence of a branch. *(#20, #22.)*

### Docs & spec alignment
- Keep the design doc and code in lockstep (paths, field names, examples). Honor exact contract details (e.g. `?include[]=rubric_assessment`). When an ADR decision changes, follow [ADR-0019](./decisions/0019-adr-governance-and-lifecycle.md). *(#20, #22.)*

### Project-specific
- **Don't spoon-feed the LLMs** — mock data/events must mirror real-world signal availability so the Decision Services are genuinely tested (e.g. badge acceptance is *discovered* via a fetch, not a boolean on the event; competency-vs-sub is read from the outcome title prefix, not a flag). *(#4.)*
- **Keep the seams** — preserve future-service invocation seams even when Phase-1-stubbed, so swapping in the real service is a step-implementation change, not an executor rewrite. *(#22.)*
- **`py.typed` for libs** — shared libraries must force-include a `py.typed` marker in the wheel or downstream `mypy` fails with `import-untyped`. *(#4.)*
