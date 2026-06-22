# Skills Mobility Infrastructure

Proof of concept for AI-assisted credential orchestration, transformation, and delivery using LLMs.

## Purpose

This project is intended to validate whether an orchestration-centric architecture can:

- interpret learner and credential events,
- assemble the context needed for decisions,
- use LLMs for routing and transformation reasoning, and
- deliver transformed credential data to downstream systems.

## Repository layout

Monorepo (ADR-0001). The backend lives in `services/`, the frontend in `apps/`, and shared first-party code in `libs/`:

| Directory | What lives here |
|---|---|
| [`apps/`](./apps/) | Deployable **React + TypeScript** SPAs (demo UIs). Today: [`apps/mock-lms/`](./apps/mock-lms/) — the presenter demo console. |
| [`services/`](./services/) | Deployable **Python / FastAPI** backend services. Today: [`services/mock-lms/`](./services/mock-lms/) — Canvas-style LMS APIs + credential-event emission. |
| [`libs/`](./libs/) | Shared **first-party Python libraries** reused by services (not third-party deps). Today: [`libs/events/`](./libs/events/) — the event contracts. |
| `packages/` | Shared TypeScript / cross-stack packages (generated clients, contracts). Not yet populated. |
| `infra/` | Infrastructure as code (CDK). Not yet populated. |
| [`docs/`](./docs/) | Docs by lifecycle phase (`1_product`, `2_requirements`, `3_design`, `4_operations`) plus [`decisions/`](./docs/decisions/) (ADRs). |

Dependency direction: `apps/` may use `packages/` but not `services/`; `services/` may use `libs/` but not each other directly (they talk via APIs/events); `libs/` depends on neither.

## Getting started

Prerequisites: **Python 3.12**, [**uv**](https://docs.astral.sh/uv/), and **Node.js** (for the UI).

```bash
# Backend + shared libs (uv workspace) — from the repo root
uv sync --all-packages     # create the venv + install all workspace members
uv run mock-lms            # serve the Mock LMS API at http://127.0.0.1:8000 (OpenAPI docs at /docs)
uv run pytest              # run the full test suite
```

```bash
# Demo UI (React + Vite)
cd apps/mock-lms
npm install
npm run dev                # http://localhost:5173 (proxies /api + /demo to the backend on :8000)
```

Per-component detail and "try it" steps live in the component READMEs:
[`services/mock-lms/`](./services/mock-lms/README.md) · [`apps/mock-lms/`](./apps/mock-lms/README.md).

## Initial POC Scope

The current scope is intentionally narrow and focused on validating technical assumptions. It includes:

- mock learner and credential event generation,
- mock learner and skills data APIs,
- an orchestration workflow engine,
- context aggregation for decision-making,
- specialized LLM decision services for routing and transformation,
- deterministic policy validation,
- delivery to LearnCloud/LearnCard and SmartResume, and
- audit logging, confidence scoring, and traceability.

## Out of Scope

This POC is not intended to be production-ready. It does not currently target production Open edX eventing, full policy/governance workflows, multi-tenant concerns, human review flows, or complex exception handling.

## Success Criteria

The POC will be considered successful if it demonstrates reliable end-to-end orchestration, consistent and explainable LLM outputs, successful downstream delivery, and complete audit logging of execution decisions and outcomes.

## Architecture & decisions

The component model and the reasoning behind it live in [`docs/3_design/`](./docs/3_design/) (start with the [POC Component Boundary Matrix](./docs/3_design/poc-component-boundaries.md)) and the ADRs in [`docs/decisions/`](./docs/decisions/). The design has evolved since the overview above — notably, the single LLM decision service is now decomposed into four specialized services (ADR-0007/0008), and a standalone MCP client layer is deferred from the initial POC (ADR-0012). The ADRs are the source of truth where they diverge from this summary.
