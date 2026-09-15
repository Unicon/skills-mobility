# Skills Mobility Infrastructure

Proof of concept for AI-assisted credential orchestration, transformation, and delivery using LLMs.

## What is Skills Mobility Infrastructure (SMI)?

Skills and achievement data have long been difficult to move between education, credentialing, and workforce systems. Even when organizations adopt standards, connecting systems often still requires one-off integrations, manual mapping, and custom transformation work that is costly to build and difficult to scale. Unicon's Skills Mobility Infrastructure is an open-source toolset being developed to address that challenge by creating a reusable way to translate, transform, and route skills-related data between systems while preserving its meaning. The current proof of concept demonstrates this approach through a working orchestration flow that triggers an event, transforms source data, and routes standards-aligned information to destinations.

This repository represents the outcome of a focused proof of concept and should be viewed as an early-stage foundation rather than a production-ready solution. The initial sprint was intentionally scoped to test the approach, identify the most significant technical challenges, and establish a base for continued development. The code is being shared openly under the Apache 2.0 license so others can explore the approach, follow its evolution, and ultimately contribute to infrastructure that can be reused and extended across skills mobility use cases. Unicon is continuing to expand the functionality and is looking for partners to test, validate, and co-design the toolset against real-world skills mobility challenges.

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
| [`apps/`](./apps/) | Deployable **React + TypeScript** SPAs (demo UIs). Today: [`apps/mock-lms/`](./apps/mock-lms/) — the presenter demo console; [`apps/admin/`](./apps/admin/) — the read-only Orchestrator observability console. |
| [`services/`](./services/) | Deployable **Python / FastAPI** backend services. Today: [`services/mock-lms/`](./services/mock-lms/) — Canvas-style LMS APIs + credential-event emission; [`services/event-consumer/`](./services/event-consumer/) — the workflow ingress boundary; [`services/orchestrator/`](./services/orchestrator/) — the Phase-1 plan executor. |
| [`libs/`](./libs/) | Shared **first-party Python libraries** reused by services (not third-party deps). Today: [`libs/events/`](./libs/events/) — the event contracts. |
| [`packages/`](./packages/) | Shared TypeScript / cross-stack packages. Today: [`packages/contracts/`](./packages/contracts/) — shared types + the Mock LMS/Orchestrator API clients; [`packages/ui/`](./packages/ui/) — design tokens + shared UI primitives. |
| `infra/` | Infrastructure as code (CDK). Not yet populated. |
| [`docs/`](./docs/) | Docs by lifecycle phase (`1_product`, `2_requirements`, `3_design`, `4_operations`) plus [`decisions/`](./docs/decisions/) (ADRs). |

Dependency direction: `apps/` may use `packages/` but not `services/`; `services/` may use `libs/` but not each other directly (they talk via APIs/events); `libs/` depends on neither.

## Getting started

Prerequisites: **Python 3.12**, [**uv**](https://docs.astral.sh/uv/), and **Node.js** (for the UI).

```bash
# Backend + shared libs (uv workspace) — from the repo root
uv sync --all-packages     # create the venv + install all workspace members
uv run pytest              # run the full test suite

# Three backends chain together — Mock LMS emits to the Event Consumer, which
# hands off to the Orchestrator — but each hop is opt-in via env var, so start
# them in this order for events to flow end-to-end:
uv run orchestrator                                                          # :8400
EVENT_CONSUMER_ORCHESTRATOR_URL=http://127.0.0.1:8400 uv run event-consumer  # :8200
MOCK_LMS_EVENT_CONSUMER_URL=http://127.0.0.1:8200 uv run mock-lms           # :8000
```

```bash
# Demo UIs (React + Vite) — npm workspace, install once from the repo root
npm install
npm run dev -w apps/mock-lms   # http://localhost:5173 (proxies /api + /demo to the backend on :8000)
npm run dev -w apps/admin      # http://localhost:5174 (proxies /executions + /healthz to the backend on :8400)
```

Per-component detail and "try it" steps live in the component READMEs:
[`services/mock-lms/`](./services/mock-lms/README.md) · [`apps/mock-lms/`](./apps/mock-lms/README.md) ·
[`services/event-consumer/`](./services/event-consumer/README.md) ·
[`services/orchestrator/`](./services/orchestrator/README.md) · [`apps/admin/`](./apps/admin/README.md).

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
