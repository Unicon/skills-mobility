# Pre-PR Checklist — Code PRs

Run this before opening a **code** PR (a new/changed `services/*` or `apps/*` module). It captures the standards that have come up repeatedly in review, so we address them up front instead of in a re-review round. It complements the task-completion checklist in [`AGENTS.md`](../AGENTS.md) (tests pass, lint/types clean, no secrets, no AI attribution) — this doc is the service/PR-shaped layer on top.

Derived from recurring review feedback on the first service wave (#4 Mock LMS, #20 Context Builder, #21 Event Consumer, #22 Orchestrator), the second wave (the LearnCard delivery layer #48–#61 and the LLM Decision Services #27–#79), and the third wave (the merge-train reviews #77–#107 and the fallback-visibility issues #121–#141). PR references are cited so the rationale is traceable.

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
[ ] Failed and successful records never share a store path/key (a later failure must not
    clobber a stored success — give failures their own kind, #77/#78/#85)
[ ] Replay/default fallbacks LOG when they fall through to the default fixture (#77)
[ ] Plans/templates/routing are bounded by the ACTUAL selection, not all-known-targets;
    a selection-blind step logs the divergence at failure level (#89, #112)
[ ] Values that differ per call site are explicit function parameters, not reads off a
    shared inputs dict: if the caller forgets to bind the key, `inputs.get(...)` quietly
    returns the other phase's data instead of erroring (#102 item 1)
[ ] Name reflects actual scope: target-qualify helpers/actions once a sibling family
    exists; don't reuse one field name for different semantics on different models
    (plan_source vs output_source, #78/#89/#90 item 7)
[ ] Paired/parallel implementations share a helper — duplication hides the divergence
    a shared signature would surface (#96, #102 item 6)
[ ] An executor handed an empty plan/collection fails or refuses — it must not
    return success having executed nothing (#90)

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
[ ] The HTTP-200-but-status:"failed" branch has its OWN test, distinct from the
    exception path (#87, #88, #96)
[ ] An UNRECOGNIZED enum-like value (typo/new id) exercises the fallback — not just the
    known-empty case (#89)
[ ] Required no-default env vars have a config test asserting absence raises (#87)
[ ] A negative test's fixture carries ONE fault — multi-fault fixtures pass coincidentally
    on whichever check fires first (#90 item 1)
[ ] When a real seam and a deterministic fallback can produce the same output, at least
    one test feeds an input where they DIFFER and asserts the seam's version wins — tests
    whose expected output matches the fallback pass even when the seam is silently
    bypassed (#90 item 2)
[ ] Inputs dicts are driven through the real caller/planner at least once — hand-built
    dicts hide the gap between what the caller binds and the helper expects (#102 item 1)
[ ] Every error-taxonomy branch has coverage, not just the well-trodden ones (#102 item 4)
[ ] Replay fixtures are keyed by the signal that DRIVES the decision (subject, grade,
    sub-competency), not by event_type; and fixtures satisfy the schemas they claim
    (#77, #78 item 20, #105, #127)

Docs & spec alignment
[ ] Design AND requirements docs updated to match descoped/shipped behavior — no stale example a
    contributor would copy to reintroduce a just-fixed bug (e.g. a removed `email` id path)
[ ] Design docs don't name modules/files that no sibling service actually builds
[ ] The exact API-contract details from the design doc are honored (query params, required fields)
[ ] ADR edits follow ADR-0019 (reversals stay visible: Status + Supersedes); keep fast-moving
    version details (language/model versions) out of ADRs — put them in a design doc
[ ] ADR open questions get closed IN THE ADR when a downstream doc resolves them (#111)
[ ] Cite ADR sections by NAME, never by §line-number (they drift); no bare PR-number
    cites where the rule should be stated inline (#96, #111, #115)
[ ] README parity with field-mapping's (the reference): uv sync first, a pasteable sample
    request (json_schema_extra example + curl), live-Bedrock/AWS-SSO section; auth via
    HTTPBearer/HTTPBasic so Swagger renders a working Authorize control (#77/#78/#85/#87)
[ ] User-facing READMEs don't cite AGENTS.md (internal agent instructions) (#102 item 7)
[ ] A deliberate "lighter than the FR for POC" cut is written back into the design doc,
    not left as silent under-implementation (#102 item 3, #125)

Git / PR hygiene
[ ] Stacked PR retargeted to `main` once its base merges; taken out of draft
[ ] PR body refreshed — resolved open questions removed, stale "Depends on" sections updated;
    re-check it against the PR's OWN later commits before review (#107 item 5)
[ ] The description lists EVERY issue the PR closes, so auto-close fires (#89)

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

Audit trail & fallback visibility (third wave's signature theme)
[ ] Every best-effort fallback is POSITIVELY marked on the persisted record
    (decision_source / _degraded / output_source) — never inferable only from missing
    fields or a logger.warning (#88, #90, #102, #128–#133)
[ ] Stub/degraded returns must not present as genuine success: no hardcoded
    status:"succeeded" or confidence defaults indistinguishable from a real call (#90, #102)
[ ] The FULL response envelope (confidence, rationale, artifact refs) survives into the
    persisted step output — audit parity with sibling seams (#88)
[ ] Any ref you emit is dereferenceable by its consumer: reader's artifact dir matches
    the writer's; on Lambda, local stores are per-instance /tmp — inline what the read
    model needs (#85 item 8, #129, #140)
[ ] Success and failure outcomes log at DIFFERENT severities (#87)

Cross-component & environment parity
[ ] After an id rename/descope: grep prose, fixtures, _EXPECTED_ test sets, and dead
    validators repo-wide — string-typed contracts drift silently (#78, #116, #124)
[ ] Exact-string producer↔consumer contracts (registry ids ↔ ACTIONS keys) get a
    registration-completeness guard test (#124, #126)
[ ] A convention introduced mid-flight (e.g. _degraded) is reconciled onto older
    in-flight branches at merge time (#131)
[ ] When two artifacts encode the same set (CI matrix vs env file, doc example vs
    contract), declare ONE authoritative and cross-reference the other (#107 item 4)
[ ] Don't index a list into a dict/Map by a field that can repeat (e.g. decisions[]
    keyed by kind): later entries silently replace earlier ones. If the key can
    legitimately repeat, keep a list per key — or split the model so it can't (#132)
[ ] Local is laxer than deployed: percent-encode bracket query params (%5B%5D — Function
    URLs/CloudFront 400 what uvicorn accepts); smoke each new surface live once (#134, #141)
[ ] IAM matches the live-proven policy (Bedrock needs inference-profile AND
    foundation-model ARNs); verify CLI flag semantics — a repeated list flag REPLACES,
    not merges (#107)
[ ] No declared-but-never-populated scaffolding: schema fields that every construction
    site leaves None, or template resources nothing consumes — delete them or wire them
    (#107 item 3, #133)
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
- **Fallback provenance is the third wave's `.env` bug** — the single most-repeated theme (five PRs, six issues): a best-effort seam that falls back must say so *on the stored record*, because the fallback's own fields lie (stub gate reports confidence 1.0; `_DEGRADED_MAPPING` reports `status:"succeeded"`). A `logger.warning` is invisible to the Admin UI and gone on Lambda. Mark it positively (`decision_source`, `_degraded`, `output_source`) and render it distinctly. *(#88, #89, #90, #102; #128–#133.)*
- **Local is laxer than deployed** — uvicorn/compose accept literal `[]` in query strings, tolerate missing IAM, and never exercise CloudFront/Function-URL behavior (auth permission pairs, origin timeouts, ASGI lifespan per event). Anything that builds URLs, policies, or CLI invocations needs one live verification per surface — three separate live-only bugs shipped past green local suites in one week. *(#134, #141, #107; the AWS bring-up.)*
- **Why cross-PR drift survives two green reviews** — each PR is reviewed and tested against its *own* base, so no reviewer or CI run ever sees the two branches combined; the first time the combination exists is the merge commit. And because these integration points are exact-string contracts wired to best-effort fallbacks, the combined failure isn't red — a plan whose action_id matches nothing quietly re-binds to the deterministic plan, a convention the older branch predates simply doesn't fire. Nothing fails, so nothing gets noticed. That's why the reconciliation bullets above are a *merge-time* step and why the guard test matters: it's the only artifact that executes against the combination. *(#121, #124, #126, #131.)*
- **Don't spoon-feed the LLMs** — mock data/events must mirror real-world signal availability so the Decision Services are genuinely tested — badge acceptance is *discovered* via a fetch, not handed over as a boolean; competency-vs-sub-competency is read from the outcome title prefix, not a flag; and content must genuinely vary per entity (108 submissions from 12 reused bodies makes titles mismatch content). *(#4, #34.)*
