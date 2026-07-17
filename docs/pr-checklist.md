# Pre-PR Checklist — Code PRs

Run this before opening a **code** PR (a new/changed `services/*` or `apps/*` module). It captures the standards that have come up repeatedly in review, so we address them up front instead of in a re-review round. It complements the task-completion checklist in [`AGENTS.md`](../AGENTS.md) (tests pass, lint/types clean, no secrets, no AI attribution) — this doc is the service/PR-shaped layer on top.

Derived from recurring review feedback on the first service wave (#4 Mock LMS, #20 Context Builder, #21 Event Consumer, #22 Orchestrator) and the second wave (the LearnCard delivery layer #48–#61 and the LLM Decision Services #27–#79). PR references are cited so the rationale is traceable.

## Quick checklist

```
Service scaffolding (new or changed service)
[ ] logging.basicConfig() in run() + a configurable <SERVICE>_LOG_LEVEL (default INFO)
[ ] logger.info() at the key transitions (not just a silent DB write) — carry ALL FOUR
    correlation ids (workflow_id, execution_id, step_id, correlation_id), failure path too
[ ] README: `uv sync --all-packages` as the first run step
[ ] README: Swagger /docs link with the concrete port
[ ] README: a manual end-to-end / smoke-test section
[ ] Port configurable via <SERVICE>_PORT; avoid the FULL Consul range (8300–8302, 8500, 8600);
    keep the port identical across code, .env.example, README, and docker-compose

Config & secrets (.env)
[ ] Settings actually LOAD .env — pydantic SettingsConfigDict(env_file=..., env_prefix=...);
    Node: process.loadEnvFile()/dotenv. env_prefix alone loads nothing (silent empty defaults).
[ ] env_file anchored to an absolute package-relative Path(__file__) path, not a bare ".env"
    (a relative path resolves against the CWD; services are run from the repo root)
[ ] A regression test instantiates Settings from a DIFFERENT cwd than where .env lives
    (not monkeypatch.chdir into the same dir — that never exercises the real mismatch)
[ ] .env.example covers every new env var
[ ] Config constants — incl. non-secret identity labels — live in .env/.env.example, not
    hardcoded in source (the platform is multi-org; hardcoding blocks per-org
    customization without a code edit)

Code & API
[ ] Closed value sets are Literal/StrEnum, not str (turn the documenting comment into the type)
[ ] HTTP clients call resp.raise_for_status() — never swallow a non-2xx
[ ] Fail loudly: raise on an unknown enum/prefix (don't silently default to a bucket); catch
    only the specific expected error (no catch-all that swallows a real failure as success)
[ ] No silent drops: surface/document discarded items; advance status fields through states
[ ] Names reflect the concept; REST verb/path matches the action (a toggle is a PUT, not a POST)
[ ] Hard-coded "magic" values are configurable (env/CLI) and documented in the README
[ ] Non-obvious models / branches carry a one-line docstring or comment

Tests
[ ] The primary endpoint is tested at the HTTP layer (happy path + a malformed/422), not just /healthz
[ ] Every declared query param exercised — incl. the empty / no-match case and ordering,
    not just the populated happy path (a happy-path-only test hid a `total` undercount, #32)
[ ] Failure/retry paths test EXHAUSTION + error normalization (an SDK-shaped rejection),
    not just retry-then-succeed
[ ] Mocks cover the full documented flow (e.g. profile lookup) and match the documented output
    shape — a mock must not hide an unimplemented step
[ ] Assertions check REAL data on every output key — not presence-only against empty stubs
[ ] Assert invariants explicitly (e.g. `len(calls) == 1`), not via an incidental uncaught exception
[ ] Tricky pure helpers have direct unit tests (edge cases), not just indirect integration coverage
[ ] Tests assert the behavioral consequence of a flag/branch, not just that the toggle flips

Docs & spec alignment
[ ] Design AND requirements docs updated to match descoped/shipped behavior — no stale example a
    contributor would copy to reintroduce a just-fixed bug (e.g. a removed `email` id path)
[ ] Design docs don't name modules/files that no sibling service actually builds
[ ] The exact API-contract details from the design doc are honored (query params, required fields)
[ ] ADR edits follow ADR-0019 (reversals stay visible: Status + Supersedes); keep fast-moving
    version details (language/model versions) out of ADRs — put them in a design doc

Git / PR hygiene
[ ] Stacked PR retargeted to `main` once its base merges; taken out of draft
[ ] PR body refreshed — resolved open questions removed, stale "Depends on" sections updated

Project-specific
[ ] Mock data/events do NOT bake in answers the LLM Decision Services are meant to discern;
    content varies per real entity (per-course, not a shared per-subject pool) so titles match content
[ ] Each LLM Decision Service owns its own registry/catalog directly — the orchestrator does NOT
    fetch and inject it
[ ] Deterministic validation checks policy/contract conformance; it does NOT grade the LLM's task
    for it (required-step / required-output "did the model do its job" checks belong in the test
    harness, not a runtime failure gate)
[ ] Policy Rules Service kept explicitly out of POC scope in docs (mark any dependency a future phase)
[ ] Future-service seams are present even when Phase-1-stubbed (input bindings, no-op steps)
[ ] New libs ship a py.typed marker (force-included in the wheel) so consumers' mypy passes
```

## Notes (the why)

Only the items whose rationale isn't self-evident from the checklist above — the rest speak for themselves.

- **`.env` must be *loaded*, not just written** — the second wave's single most-repeated bug. In pydantic-settings, `SettingsConfigDict` with only `env_prefix` set never reads the file; you must also set `env_file`. Without it every value silently defaults to empty and the first request crashes (`Authorization: Bearer ` → `Illegal header value`). Node provisioning scripts have the same trap — call `process.loadEnvFile()`/`dotenv`. *(#49, #50, #51, #54, #55, #56, #59 — seven PRs.)*
- **Four correlation identifiers on every log line** — a systemic copy-paste template gap Mary flagged "four for four" (Issuer Adapter, Wallet Adapter, Profile Resolver, Delivery Router). Log `workflow_id`, `execution_id`, `step_id`, and `correlation_id` — especially on the failure path, and consider preserving them in the result record — so a run is traceable end to end. *(#48, #50, #51, #56.)*
- **Logging setup** — uvicorn doesn't configure app loggers, so without `logging.basicConfig(level=settings.log_level.upper())` in `run()` your `logger.info()` calls are silently dropped. Log the audit-relevant transitions (ingress/gate decision, plan reuse-vs-generate, per-step execution, fetch attempts), not just the DB write. *(#20 FR-CB15, #21, #22.)*
- **README `uv sync` first** — the service isn't importable as a workspace member until installed, so a README whose first step isn't `uv sync --all-packages` fails for anyone but the author; order the smoke-test steps so they don't 404 against each other. *(#4, #20, #21, #22.)*
- **Port allocation** — avoid clashes and Consul's *full* reserved range (8300–8302, 8500, 8600), which bites under Docker Desktop; the recurring miss was picking 8500/8600 anyway, then leaving stale ports in `.env.example`/README/compose. Landmarks: Mock LMS 8000, Context Builder 8100, Event Consumer 8200, Orchestrator 8400; wallet adapter 8900, issuer 8910. *(#22, #48, #50, #56, #61.)*
- **Validation vs. grading the LLM** — deterministic validation of a Decision Service's output should check *policy/contract conformance* (schema, registry conformance, binding resolvability), not grade whether the model did its job well. Gating a service failure on "did the plan include the required steps" risks the model learning to satisfy the validator rather than produce a good plan; assert step/output presence in the test harness (Layer B) instead. *(#75.)*
- **Fail loudly on unknown input** — the flip side of "no silent drops": a helper that defaults an unrecognized course prefix to `"accounting"`, or a catch-all that treats any `createProfile` error as "already exists", hides real problems. Raise on the unexpected; catch only what you expect. *(#34, #54.)*
- **Don't spoon-feed the LLMs** — mock data/events must mirror real-world signal availability so the Decision Services are genuinely tested — badge acceptance is *discovered* via a fetch, not handed over as a boolean; competency-vs-sub-competency is read from the outcome title prefix, not a flag; and content must genuinely vary per entity (108 submissions from 12 reused bodies makes titles mismatch content). *(#4, #34.)*
