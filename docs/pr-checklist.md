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

Only the items whose rationale isn't self-evident from the checklist above — the rest speak for themselves.

- **Logging** — the non-obvious part: uvicorn doesn't configure app loggers, so without `logging.basicConfig(level=settings.log_level.upper())` in `run()` your `logger.info()` calls are silently dropped. Log the audit-relevant transitions (ingress/gate decision, plan reuse-vs-generate, per-step execution, fetch attempts), not just the DB write. *(#20 FR-CB15, #21, #22 — context-builder is the reference pattern.)*
- **README `uv sync` first** — the service isn't importable as a workspace member until installed, so a README whose first step isn't `uv sync --all-packages` fails for anyone but the author; order the smoke-test steps so they don't 404 against each other. *(#4, #20, #21, #22.)*
- **Port allocation** — avoid clashes: Mock LMS 8000, Context Builder 8100, Event Consumer 8200, Orchestrator 8400 — and steer clear of Consul's reserved range (8300–8302, 8500, 8600), which bites under Docker Desktop. *(#22.)*
- **Surface failures** — the point beyond `raise_for_status()`: advancing status fields through their documented states (`created → handoff_sent`, …) is what makes the persisted record informative for the audit trail. *(#20, #21.)*
- **Don't spoon-feed the LLMs** — the subtlest and most important one: mock data/events must mirror real-world signal availability so the Decision Services are genuinely tested — e.g. badge acceptance is *discovered* via a fetch, not handed over as a boolean on the event; competency-vs-sub-competency is read from the outcome title prefix, not a flag. *(#4.)*
