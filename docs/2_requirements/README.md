# 2 — Requirements

**Intent:** Capture *what* the system must do — scope, actors, functional and non-functional requirements, and success criteria — at both the system level and per component.

## Contents

| Doc | Scope |
|---|---|
| [`poc-requirements.md`](./poc-requirements.md) | **Master** POC requirements — scope/definitions, objectives, the full component breakdown, success criteria |
| **Mock LMS** (source-system component, three parts ↓) | |
| [`mock-lms-event-producer.md`](./mock-lms-event-producer.md) | Emits credential events (skill mastered, course completed, badge awarded); Actions, payloads, repeatability |
| [`mock-lms-apis.md`](./mock-lms-apis.md) | Canvas-style **LMS Resource APIs** the Context Builder reads; seeded data model |
| [`mock-lms-ui.md`](./mock-lms-ui.md) | Presenter-facing demo console (course-centric inspect + trigger + live emission feed) |

## Mock LMS overview

The **Mock LMS** stands in for a real LMS (Open edX in production; modeled on **Canvas LMS** for the POC). It is the POC's *source system* and has three parts, kept as separate requirements docs because they serve distinct purposes:

- **Event Producer** — publishes credential events onto the bus.
- **LMS Resource APIs** — Canvas-style read endpoints the Context Builder queries for decision context.
- **Demo UI** — a console that makes the downstream AI orchestration *legible and repeatable* for a stakeholder demo: inspect the source data, trigger an Action, watch the event stream, then compare the issued badge against the source.

**Shared scope.** In: a read-only Canvas-style API over seeded data; an emission control API publishing Canvas Live Events–shaped payloads; version-controlled, repeatable demo data; a React SPA. Out: real Canvas parity, writes/mutations through the APIs, the downstream orchestration/LLM/policy/delivery, production auth, multi-tenant concerns.

**Auth (POC):** CloudFront-layer per ADR-0002 (decided — not Cognito), a **single demo user** (no separate instructor/admin roles).

## Conventions

- One requirements doc per component, named after the component. The Mock LMS currently spans three (`mock-lms-event-producer.md`, `mock-lms-apis.md`, `mock-lms-ui.md`); the `mock-lms-` prefix is specific to those — other components (Context Builder, Policy Rules, the LLM Decision Services, etc.) won't carry it. Each doc references the master `poc-requirements.md` and relevant ADRs in [`../decisions/`](../decisions/) rather than restating them. Design lives in [`../3_design/`](../3_design/).

## Workflows

- **Archiving:** set `Status: Superseded` (note the replacement) and move retired requirements to `2_requirements/archive/`.
