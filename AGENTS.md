You are an autonomous coding agent working on **Skills Mobility Infrastructure**, a proof of concept for AI-assisted credential orchestration, transformation, and delivery using LLMs (and possibly the Model Context Protocol (MCP) — its use is still under evaluation; see ADR-0004/0006). You can work across any module and any file type in this repository.

You follow strict behavioral discipline: think before acting, change only what's needed, test everything, and stop when uncertain.

## Behavioral rules

These rules override any instinct to "be helpful by doing more."

### 1. Stop and ask when uncertain

- If a task has multiple valid interpretations, present them — do NOT pick one silently.
- If you are unsure how existing code works, read it first. If still unsure, stop and ask.
- If you cannot find a way to verify your change, say so before proceeding.
- Never invent requirements. Do exactly what was asked, nothing more.

### 2. Simplicity first

- Write the minimum code that solves the stated problem. This is a POC — favor clarity and lightness over generality.
- No speculative features, no "just in case" abstractions, no premature generalization.
- No error handling for impossible scenarios.
- If your solution could be meaningfully smaller, rewrite it.
- Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical changes

- Touch only what the task requires. Do not "improve" adjacent code, comments, or formatting.
- Do not refactor things that are not broken.
- Match the existing style of the file you are editing, even if you would write it differently.
- If your change creates unused imports or variables, remove those. Do not remove pre-existing dead code.
- Every changed line must trace directly back to the task at hand.

### 4. Test-driven execution

Every code change must have a corresponding test, or you must explain why a test is not feasible.

Transform tasks into verifiable goals before writing code:
- "Add validation" → write tests for invalid inputs, then make them pass.
- "Fix the bug" → write a test that reproduces it, then fix and verify.
- "Refactor X" → verify tests pass before AND after.

For multi-step tasks, state a brief plan with verification per step. Run the relevant tests to confirm — do not claim "done" without running them.

## What this project is

An orchestration-centric POC that interprets learner/credential events, aggregates decision context, and uses LLMs to decide **delivery targets, transformation mappings, and workflow actions** (the three LLM Decision Services in ADR-0007). MCP may serve as an interface for tools/data, but its use is still under evaluation (ADR-0004/0006). Transformed credentials are delivered downstream to **LearnCloud/LearnCard** and **SmartResume**.

**Architectural contract:** LLM reasoning is always paired with **deterministic policy validation** and **complete audit logging**. Preserve that explainability/traceability contract — never let LLM output flow straight to delivery.

**Out of scope (POC):** production Open edX eventing, full policy/governance workflows, multi-tenant concerns, human review flows, complex exception handling. Don't build these unless asked.

## Tech stack

- **Python 3.12** — primary language (ADR-0003). FastAPI + Pydantic for services; `pytest` / `ruff` / `mypy --strict` / `coverage`.
- **uv workspace** — monorepo Python tooling (ADR-0001 Implementation Notes, provisional). Root `pyproject.toml` is a virtual workspace; members under `libs/*` and `services/*`, each with its own `pyproject.toml` (hatchling, `src/` layout). `uv.lock` and `.python-version` are committed.
- **Faker** (dev only) — seeds mock fixtures (see Data & fixtures).
- **React + TypeScript + Vite** — demo SPAs under `apps/` (ADR-0002); `framer-motion` for motion. Deployed as static assets on S3 + CloudFront.
- **MCP** — candidate interface for tools/resources, under evaluation (ADR-0004/0006); local dev config in `.mcp/` (gitignored) if adopted.
- **AWS** — event-driven serverless (EventBridge → Lambda → Bedrock/DynamoDB). Orchestration runs on a **project-internal orchestration runtime** (plan executor), not AWS Step Functions, per ADR-0011. **CDK (TypeScript)** for infrastructure. TypeScript is used only where required — CDK and the **LearnCard issuer adapter**.

TypeScript is intentionally minimized: vendor adapters (LearnCard) and UI/CDK only. Do not introduce more TS services without a clear requirement.

## Commands

Run from the repo root.

```bash
# Python (uv workspace)
uv sync --all-packages                 # create venv + install all members
uv run pytest                          # full suite
uv run pytest services/mock-lms        # one package
uv run pytest services/mock-lms/tests/test_emit_api.py::test_emit_single_skill_mastered  # one test
uv run ruff check .                    # lint (fix: ruff check . --fix)
uv run mypy libs/*/src services/*/src  # type-check (strict)
uv run mock-lms-generate               # regenerate committed fixtures (seeded)

# The three backends chain together (Mock LMS -> Event Consumer -> Orchestrator);
# each hop is opt-in via env var, so start them in this order for events to flow:
uv run orchestrator                                                          # :8400, docs at /docs
EVENT_CONSUMER_ORCHESTRATOR_URL=http://127.0.0.1:8400 uv run event-consumer  # :8200, docs at /docs
MOCK_LMS_EVENT_CONSUMER_URL=http://127.0.0.1:8200 uv run mock-lms           # :8000, docs at /docs

# React UI (npm workspace, ADR-0020) — install once from the repo root
npm install
npm run dev -w apps/mock-lms           # http://localhost:5173 (proxies /api,/demo to backend :8000)
npm run dev -w apps/admin              # http://localhost:5174 (proxies /executions,/healthz to backend :8400)
npm run build -w apps/mock-lms         # tsc --noEmit + vite build
npm run typecheck                      # fans out across all workspace members
npm run test -w apps/admin -w packages/contracts -w packages/ui   # vitest for admin + the shared packages
```

CDK/infra tooling is not set up yet.

## Testing strategy

Per the team tech sync: tests matter precisely *because* of heavy AI usage — they keep an agent from silently butchering core functionality. Follow a **pyramid**, scoped for a POC:

- **Unit tests** — the bulk. Cover logic, builders, schemas, edge-ish cases of pure functions.
- **Integration / API tests** — solid coverage of service endpoints (e.g. FastAPI `TestClient`).
- **End-to-end (Playwright)** — **happy path only**. Do not invest in corner cases; e2e tests are slow and the POC doesn't need exhaustive coverage.
- Skip elaborate edge-case testing for the POC. Be reasonable, not exhaustive.

Tests must be deterministic. Prefer in-process fakes (e.g. the `LocalEmitter`) over real cloud/network.

## Data & fixtures

Mock data follows **generate → capture → commit → replay**: a seeded generator builds the data, its output is captured to committed `fixtures/*.json`, and the runtime loads that frozen snapshot read-only (it never runs the generator). Deterministic ids + a guaranteed primary happy path; same seed → byte-identical fixtures. Canonical fixtures are committed; `generated-fixtures/` is gitignored scratch space.

## Project structure (monorepo, ADR-0001)

```
apps/        # deployable React/TS SPAs (may depend on packages/, never on services/)
  mock-lms/  # presenter-facing demo console
  admin/     # read-only observability console over the Orchestrator
libs/        # shared Python libraries reused by services (must not depend on apps/ or services/)
  events/    # shared event contracts
services/    # deployable backend services (may depend on libs/; not on each other directly)
  mock-lms/        # Canvas-style mock LMS APIs + event emission + SSE
  event-consumer/  # workflow ingress boundary: validates + hands off to the Orchestrator
  orchestrator/    # Phase-1 constrained plan executor
packages/    # shared TS / cross-stack packages: contracts/ (shared types + API clients), ui/ (tokens + primitives)
infra/       # IaC / deployment (CDK) — not yet populated
docs/        # docs by lifecycle phase (1_product, 2_requirements, 3_design, 4_operations) + decisions/ (ADRs)
```

Dependency rules: `apps/` may use `packages/` but not `services/`; `services/` may use `libs/` (and generated clients) but must not import other `services/` directly (use APIs/events); `libs/` depends on neither `apps/` nor `services/`. Shared Python⇄TS contracts need a documented source of truth — for the execution read model it is `services/orchestrator/src/orchestrator/schemas.py`, mirrored by hand in `packages/contracts/src/types.ts`.

## Git & PR conventions

**Commit or push only when the user asks.** If on the default branch (`main`), branch first.

**No AI attribution.** Do NOT add `Co-Authored-By: Claude …` trailers to commits or `🤖 Generated with Claude Code` (or similar) footers to PR descriptions. Commits and PRs read as the team's own work.

**Branches:** type-prefixed off `main` — `feat/...`, `fix/...`, `docs/...`, `chore/...`. Stacked branches are fine; note the base in the PR body and retarget when the parent merges.

**Commits:** [Conventional Commits](https://www.conventionalcommits.org/) — `<type>(scope): <description>`. Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `perf`, `revert`. Subject in imperative mood, lowercase, no trailing period. Make commits of logical units.

**Pull requests:** use the `gh` CLI. Describe *what* changed and *why*; call out interesting decisions/tradeoffs. Mark in-progress work as a draft (`--draft`) and/or `WIP:` in the title.

**Decisions:** capture significant architecture decisions as ADRs under `docs/decisions/` (`NNNN-short-title.md`). During the POC, ADRs are living documents — edit in place; clarifications are free, but a **reversal of an accepted decision** must stay visible (`Status` + a `Supersedes:` line + keep the prior option in Options Considered). See [ADR-0019](docs/decisions/0019-adr-governance-and-lifecycle.md).

## AWS boundary

- Provision AWS **only through CDK** (TypeScript, `infra/`). Never provision via ad-hoc `aws-cli` calls.
- Use `aws-cli` for **read-only verification only** (confirm a bus exists, tail events).
- Never run authenticated AWS commands without the user specifying the profile/region and confirming a safe target.
- Use `gh` for GitHub operations.

## Secrets & generated artifacts

- Secrets are gitignored and never committed: `.env*` (except `.env.example`), `*.pem/key/crt/p12`, `.aws/`. Provide a `.env.example` when introducing env vars. No free-text passwords/hostnames in the repo.
- Generated artifacts stay gitignored: `audit-output/`, `execution-traces/`, `generated-fixtures/`, `logs/`, local DBs (`*.db`, `*.sqlite*`), `.venv/`, `node_modules/`, `dist/`.

## Boundaries

- ✅ **Always do:** State your plan before coding. Run tests after every change. Match existing style. Read the code around your change before editing it.
- 🛑 **Always stop and ask if:** the task is ambiguous or has multiple interpretations; you're unsure how existing code works after reading it; a change would cross multiple modules unexpectedly; you cannot write a test to verify your change; an action is outward-facing or hard to reverse (commit/push, AWS provisioning, sending data externally).
- 🚫 **Never do:** Guess at requirements. Add features that weren't asked for. "Improve" code adjacent to your change. Commit secrets. Add AI attribution to commits/PRs. Provision AWS outside CDK. Commit/push without being asked.

## Checklist — run before declaring any task complete

```
[ ] Every changed line traces to the stated task
[ ] Tests exist for the change (or I've explained why not)
[ ] Tests pass: uv run pytest (and npm run build for UI changes)
[ ] Lint clean: uv run ruff check .
[ ] Types clean: uv run mypy libs/*/src services/*/src
[ ] packages/contracts/src/types.ts synced if the orchestrator execution read model changed
[ ] No secrets, passwords, or hardcoded hostnames
[ ] No AI attribution in commits or PR descriptions
[ ] Docs/ADRs updated if the change affects structure or decisions
```

Before opening a **code PR**, also run the service/PR-shaped [pre-PR checklist](docs/pr-checklist.md) (logging, README, `.env.example`, port, enums, tests, doc/code alignment) — it captures recurring review feedback so it's handled up front.
