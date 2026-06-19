# Phase 1 POC Slice Requirements

Status: Draft
Date: 2026-06-19
Related: [POC Requirements](./poc-requirements.md) · [Target POC Requirements](./target-poc-requirements.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Mock LMS Event Producer](./mock-lms-event-producer.md) · [Mock LMS APIs](./mock-lms-apis.md) · [Mock LMS UI](./mock-lms-ui.md) · [Mock LMS Design](../3_design/mock-lms.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md)

## 1. Purpose

This document defines the **Phase 1 implementation slice** for the POC: a fast, functional end-to-end pipeline that the team can build on in later phases.

The goal of Phase 1 is **not** to prove the full target architecture. The goal is to get a working end-to-end flow in place quickly while preserving enough component boundaries that later phases can layer in richer orchestration, policy validation, and LLM-driven decision-making.

## 2. Primary Happy Paths

Phase 1 should prove two supported event types:

1. `skill_mastered`
2. `course_completed`

For each supported event type, the Phase 1 happy path is:

1. A demo operator triggers the event from the Mock LMS UI.
2. The Mock LMS Event Producer publishes the event and the Event Consumer accepts it.
3. The Orchestrator starts a workflow run.
4. The Context Builder uses deterministic configuration to decide which Mock LMS Resource APIs to fetch for the given event type and returns the required source data to the Orchestrator.
5. The Orchestrator converts just enough of that source data into the input Open Badges 3.0 payload required by the LearnCard Issuer Adapter.
6. The Orchestrator sends that payload to the Delivery Router.
7. The Delivery Router sends the payload to the LearnCard Issuer Adapter.
8. The LearnCard Issuer Adapter returns the issued and signed Open Badges 3.0 badge to the Delivery Router, which returns it to the Orchestrator.
9. The Orchestrator makes any additional payload adjustments needed to prepare input for the LearnCard Wallet Adapter.
10. The Orchestrator sends that wallet-input payload to the Delivery Router.
11. The Delivery Router sends the payload to the LearnCard Wallet Adapter.
12. The workflow records the final outcome for later inspection.

## 3. In Scope

Phase 1 includes:

- The **Mock LMS Demo UI**, **Mock LMS Event Producer**, and **LMS Resource APIs**
- The `skill_mastered` and `course_completed` event types
- The **Event Consumer** as a thin ingress boundary
- The **Orchestrator** as the execution runtime
- The **Context Builder** with deterministic configuration mapping event type to required Mock LMS Resource API fetches
- Direct payload preparation inside the **Orchestrator** for the LearnCard Issuer Adapter input
- The **Delivery Router**
- The **LearnCard Issuer Adapter**
- Direct payload preparation inside the **Orchestrator** for the LearnCard Wallet Adapter input after issuer response
- The **LearnCard Wallet Adapter**
- Correlated workflow logging or execution records sufficient to inspect a run after completion

## 4. Out of Scope for Phase 1

Phase 1 does not require:

- The **Workflow Actions LLM Decision Service**
- The **Delivery Targets LLM Decision Service**
- The **Field Mapping LLM Decision Service**
- The **Field Synthesis LLM Decision Service**
- The **Transformation Executor** as a separate component
- The **Policy Rules Service**
- The **Admin UI**
- The `badge_awarded` event type as a required end-to-end flow
- **SmartResume** delivery
- A standalone MCP Client Layer
- Multi-target delivery in the same execution
- Tracking logging data in the orchestrator that might have been made available to the Admin UI
- Rich configuration management UIs for policies, mappings, targets, or action registries
- Human review flows
- Complex branching or exception-heavy workflows
- Production-scale observability infrastructure

## 5. Functional Requirements

- **FR-P1-1** The Mock LMS UI SHALL allow an operator to trigger the Phase 1 supported event types: `skill_mastered` and `course_completed`.
- **FR-P1-2** The Event Consumer SHALL validate the incoming event envelope, enforce ingress idempotency, create an execution identifier, and hand off the run to the Orchestrator.
- **FR-P1-3** The Context Builder SHALL use deterministic configuration keyed by event type to determine which Mock LMS Resource APIs and resources must be fetched.
- **FR-P1-4** The Context Builder SHALL return the fetched source data to the Orchestrator in a form the Orchestrator can use for Phase 1 payload preparation.
- **FR-P1-5** The Orchestrator SHALL convert the fetched source data into the minimum Open Badges 3.0 input payload required by the LearnCard Issuer Adapter.
- **FR-P1-6** The Orchestrator SHALL send the issuer-input payload to the Delivery Router.
- **FR-P1-7** The Delivery Router SHALL invoke the LearnCard Issuer Adapter and return the issued signed badge to the Orchestrator.
- **FR-P1-8** The Orchestrator SHALL make any necessary additions or adjustments to the issued badge so it is prepared as input to the LearnCard Wallet Adapter.
- **FR-P1-9** The Orchestrator SHALL send the wallet-input payload to the Delivery Router.
- **FR-P1-10** The Delivery Router SHALL invoke the LearnCard Wallet Adapter.
- **FR-P1-11** Phase 1 SHALL avoid introducing LLM planning, LLM routing, or deterministic policy gating as required runtime dependencies for the happy path.

## 6. Boundary Rules for Phase 1

- The Event Consumer must remain thin; orchestration logic should not accumulate there.
- The Context Builder owns the deterministic mapping from event type to Mock LMS Resource API fetches.
- The Orchestrator owns Phase 1 payload preparation for both LearnCard Issuer Adapter input and LearnCard Wallet Adapter input. This will only be temporarily owned by the Orchestrator until the other services are added in future phases.
- The Delivery Router and adapters own transport and adapter invocation; they do not decide what event data to fetch or how the business workflow should proceed.
- The Mock LMS remains split between event production and read APIs even in the first slice.
- Phase 1 should not collapse everything into one handler merely for speed; it should stay buildable into later phases.

## 7. Acceptance Criteria

Phase 1 is complete when the team can demonstrate all of the following:

- A `skill_mastered` event can run end to end through the Phase 1 pipeline.
- A `course_completed` event can run end to end through the Phase 1 pipeline.
- For each supported event type, the Orchestrator prepares issuer input, the LearnCard Issuer Adapter returns a signed Open Badges 3.0 badge, and the Orchestrator then prepares and sends wallet input through the Delivery Router.
- The happy paths are repeatable locally with deterministic source data.
- The implementation leaves clear room for later phases to add Policy Rules, specialized LLM services, richer payload transformation, and the Admin UI without replacing the basic pipeline.
