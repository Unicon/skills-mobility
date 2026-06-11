# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Early build-out. The first code has landed: the **Mock Event Producer** (the "Mock LMS"), as a uv workspace.

- `libs/events/` — `skills-mobility-events`: shared event contracts (Pydantic envelope + body schemas).
- `services/mock-lms/` — `mock-lms`: Canvas-style mock LMS metadata APIs + credential event emission + SSE feed (FastAPI).
- `apps/mock-lms/` — `mock-lms-ui`: presenter-facing demo console (React + TypeScript + Vite).
- `pyproject.toml` — uv workspace root (virtual); `.python-version` pins 3.12.

`packages/` and `infra/` remain unpopulated (generated TS contracts and CDK are not built yet). See `docs/decisions/0001-repo-structure.md` (Implementation Notes) and `docs/3_design/mock-event-producer.md` (build order).

## What this project is

A proof of concept for **AI-assisted credential orchestration** — interpreting learner/credential events, aggregating decision context, using LLMs for routing and transformation reasoning, and using **Model Context Protocol (MCP)** as the standard interface for tools and data. Transformed credential data is delivered downstream to **LearnCloud/LearnCard** and **SmartResume**.

The intended end-to-end pipeline (per `README.md`):

1. **Event generation** — mock learner and credential events
2. **Context aggregation** — assemble learner + skills data needed for a decision (via mock data APIs)
3. **Orchestration workflow engine** — drives the steps
4. **LLM decision service** — routing and transformation reasoning
5. **Deterministic policy validation** — non-LLM guardrail over LLM output
6. **MCP-based tool/resource access**
7. **Downstream delivery** — LearnCloud/LearnCard, SmartResume
8. **Audit logging, confidence scoring, traceability** — recorded for every decision

A key architectural intent: LLM reasoning is always paired with **deterministic policy validation** and **complete audit logging**. New work should preserve that explainability/traceability contract rather than letting LLM output flow straight to delivery.

### Explicitly out of scope (POC)

Production Open edX eventing, full policy/governance workflows, multi-tenant concerns, human review flows, complex exception handling. Don't build these unless asked.

## Planned tech stack

Inferred from `.gitignore` (no manifests exist yet to confirm exact tooling):

- **Python** — with `pytest` (testing), `ruff` (lint), `mypy` (type checking), `coverage`
- **AWS** — CDK (`cdk.out/`, `cdk.context.json`), Lambda, and SAM/Serverless build artifacts; this is intended to deploy as serverless infrastructure
- **MCP** — local dev config via `.mcp/` and `mcp-config.local.json` (gitignored)

Python tooling is now set up as a **uv workspace** (provisional — see ADR-0001 Implementation Notes). Commands, run from the repo root:

```bash
uv sync --all-packages                  # create venv + install all workspace members
uv run pytest                           # full test suite
uv run pytest services/mock-lms         # one package
uv run pytest services/mock-lms/tests/test_emit_api.py::test_emit_single_skill_mastered  # one test
uv run ruff check .                      # lint
uv run mypy libs/events/src services/mock-lms/src   # type-check
uv run mock-lms                          # run the service (http://127.0.0.1:8000, docs at /docs)
```

The React UI (`apps/mock-lms`) uses npm + Vite + TypeScript:

```bash
cd apps/mock-lms && npm install
npm run dev         # http://localhost:5173 (proxies /api,/demo to the backend on :8000)
npm run build       # tsc --noEmit + vite build
```

CDK/infra tooling is not set up yet.

## Conventions to watch

- **Secrets**: `.env*` (except `.env.example`), `*.pem/key/crt/p12`, and `.aws/` are gitignored. Provide an `.env.example` when introducing env vars.
- **Generated artifacts** are gitignored and should stay that way: `audit-output/`, `execution-traces/`, `generated-fixtures/`, `logs/`, local DBs (`*.db`, `*.sqlite*`).
