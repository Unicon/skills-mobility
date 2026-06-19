# POC Component Boundary Matrix

Status: Draft
Date: 2026-06-17
Related: [Stakeholder POC Requirements](../2_requirements/poc-requirements.md) · [Target POC Requirements](../2_requirements/target-poc-requirements.md) · [Target POC Architecture](./architecture/target-poc-architecture.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0004](../decisions/0004-lif-usage.md) · [ADR-0005](../decisions/0005-schema-mapping-langauge.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md)

## 1. Purpose

This document defines the **target component boundaries** for the POC: what each component owns, what it explicitly does **not** own, what it consumes and produces, and what other components it depends on.

This matrix reflects the accepted decomposition in ADRs 0007, 0008, and 0009. In particular, the original single **LLM Decision Service** from the POC requirements is treated here as multiple specialized components plus a deterministic transformation executor.

For this revision, the previously-mentioned **MCP Client Layer** is treated as **deferred / out of current POC scope**. This explicitly supersedes the "Utilize MCP as a standardized interface layer" objective from the stakeholder baseline in [POC Requirements](../2_requirements/poc-requirements.md); the current working expectation is captured in [Target POC Requirements](../2_requirements/target-poc-requirements.md), and the rationale and consequences are captured in [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md). If the team later identifies a concrete MCP use case, it can be reintroduced as a support dependency of the Context Builder rather than as a top-level planning component.

## 2. Boundary Matrix

"Depends on" lists direct runtime dependencies only — what this component directly calls, invokes, or reads at runtime. Upstream callers and components that pass inputs to this component are not listed.

| Component | Owns | Explicitly does not own | Primary inputs | Primary outputs | Depends on |
| --- | --- | --- | --- | --- | --- |
| **Mock LMS Demo UI** | Demo operator workflow: inspect seeded course data, trigger Actions, watch emitted events, view correlation ids | Event schema ownership, event publication mechanics, downstream orchestration logic | Operator actions; service responses; live emission feed | Action requests; read requests; operator-visible event timeline | Mock LMS Event Producer; LMS Resource APIs |
| **Admin UI** | Per-event and per-workflow operational view: execution progress, step status, confidence scores, rationale, and step inputs/outputs appropriate for review | Triggering LMS events; owning workflow execution state; raw service-to-service orchestration | Execution summaries; step-level results/responses; query responses from orchestration read APIs; optional live execution events | Workflow drill-down requests; operator-visible execution views | Orchestrator read API (unified execution model — see §6) |
| **Mock LMS Event Producer** | Canonical mock event creation; Action execution; event and correlation id generation; publish to event bus | Read-only LMS data APIs; context aggregation; orchestration; transformation; policy; delivery | Demo Action requests; seeded LMS data | Structured event envelopes on the bus; synchronous emit response to UI | Seeded LMS data; event bus |
| **LMS Resource APIs** | Read-only Canvas-style source APIs over seeded LMS data | Event emission; workflow execution; policy decisions; delivery logic | Read requests from UI and Context Builder | Course, enrollment, outcome, submission, rubric, badge, and profile resources | Seeded LMS data |
| **Event Consumer** | Workflow ingress; envelope validation; primary event-level idempotency check; creation of execution identifier; handoff into the Orchestrator | Context building; planning; mapping; policy reasoning; delivery | Events from event bus | Workflow start request; initial execution record | Event bus; Orchestrator; idempotency store |
| **Orchestrator (execution runtime)** | Execute the validated workflow plan; maintain step state; pass outputs between steps; handle retries, timeouts, and trace capture; publish and expose execution progress for the Admin UI | Authoring the workflow plan itself; source data ownership; target selection; mapping generation; delivery target API specifics | Workflow start request; validated plan; step results | Step invocations; updated execution state; final workflow outcome; execution-status events; execution detail read model/API | Workflow Actions LLM Decision Service; Delivery Targets LLM Decision Service; Field Mapping LLM Decision Service; Field Synthesis LLM Decision Service; Transformation Executor; Context Builder; Policy Rules Service; Delivery Router; execution log store |
| **Context Builder** | Assemble normalized decision context from source data and supporting systems; deterministically choose which source APIs/resources to fetch based on event type and workflow step | Plan generation; deterministic policy enforcement; payload delivery | Event from Orchestrator | Decision context bundles for planning, routing, mapping, and validation | LMS Resource APIs; internal context/config stores; source-fetch rules |
| **Workflow Actions LLM Decision Service** | Generate the complete abstract orchestration plan, including which major steps to include, skip, or conditionally execute | Executing the plan; selecting concrete delivery targets; generating transformation mappings; performing delivery; selecting source context data or creating a plan for the Context Builder | Event from orchestrator; Context from Context Builder; available service/action registry; policy context | Abstract workflow plan with confidence and rationale | Versioned Action Registry |
| **Delivery Targets LLM Decision Service** | Select the appropriate downstream delivery targets for a given event/context | Transporting data to those targets; creating target-specific payloads; policy enforcement beyond its prompt contract | Event context; learner/context data; available targets; relevant policy context | Selected delivery targets with confidence and rationale | Delivery Targets Store |
| **Field Mapping LLM Decision Service** | Generate structured mapping specifications: direct JSONata expressions plus synthesis placeholders | Generating final human-facing text; executing JSONata; selecting delivery targets | Source data; target schema; selected delivery target; credential template when applicable | Mapping specification per loop with confidence and rationale | — |
| **Field Synthesis LLM Decision Service** | Generate human-facing values for fields marked for synthesis by the Field Mapping service | Choosing which fields require synthesis; generating JSONata; executing final transformation | Synthesis placeholders and their source-data | Generated field values per loop with confidence and rationale | — |
| **Transformation Executor (JSONata / mock LIF Translator)** | Deterministic execution of JSONata mappings and substitution of synthesized values into the final target payload | LLM reasoning; field classification; natural-language generation; delivery | Source data; Lookup identifier(s) to the stored/generated mapping specification that's in Mapping Template Storage; synthesized field values; credential template when applicable | Credential template or final transformed payload | Mapping Template Storage (Mock LIF MDR) |
| **Policy Rules Service** | Deterministic validation of plans, routing constraints, required fields, transformation outputs, and delivery eligibility | Probabilistic reasoning; prompt interpretation; generating plans or mappings | Abstract workflow plan; routing/mapping outputs; transformed payloads; policy configuration | Validation results; block/allow decisions; rule violations | Policy Store |
| **Delivery Router / Target Adapters** | Invoke downstream delivery endpoints; apply adapter-specific auth/transport logic; record delivery outcomes | Choosing which targets should be used; reshaping payloads beyond adapter contract; orchestration planning | Validated transformed payload; selected targets; delivery credentials/config | Delivery results including external target acknowledgements/errors | LearnCloud/LearnCard; SmartResume |

## 3. UI Relationship

ADR-0002 established that the **Mock LMS Demo UI** and **Admin UI** are separate applications with different roles.

For the POC:

- The two UIs should remain **separate SPAs** with no required shared navigation shell.
- It is acceptable for the POC to have **no direct navigation** between them beyond operator knowledge of the two URLs.
- If low effort, a **contextual link by correlation id / event id / workflow id** is useful, but it is optional and should not expand scope significantly.

## 4. Idempotency Boundary

Idempotency should not be treated as equally owned by all components.

- The **Mock LMS Event Producer** should be **idempotency-friendly**, meaning it emits stable business identifiers plus fresh event identifiers and correlation identifiers for each run.
- The **Event Consumer** is the **primary event-ingress idempotency boundary**. It decides whether a received event has already started processing.
- The **Orchestrator** must be **retry-safe and side-effect-safe** at the execution level. This is related to idempotency, but it is not the same as ingress deduplication.

## 5. Context Fetching Rule

The decision about **which LMS APIs to fetch** should remain **deterministic inside the Context Builder**, not delegated to the Workflow Actions LLM Decision Service.

Rationale:

- Choosing source endpoints is integration plumbing with known event-to-resource relationships.
- The mapping from event type to source fetch strategy is explainable, testable, and versionable.
- The Workflow Actions LLM should decide **which high-level steps belong in the workflow**, not which concrete Canvas-style endpoints to call.

The natural implementation is a versioned set of **fetch profiles** or **context recipes** keyed by event type and, where needed, by workflow step.

## 6. Observability Model

The POC does **not** require a standalone logging microservice.

Instead:

- Each service should emit its own structured logs and step records.
- The **Orchestrator** should own the **correlated execution view** used by the Admin UI.
- The Admin UI should read a **unified execution model** keyed by event id / workflow id rather than querying every backend service independently.

This means the Orchestrator should expose either:

- a read API over persisted execution records,
- an execution event stream for live progress updates,
- or both.

For the POC, the simplest useful shape is usually:

- persisted per-workflow execution records for drill-down,
- plus optional live updates for in-progress visualization.

## 7. Supporting Stores

The following are important **logical stores** in the target POC architecture, even if several of them end up sharing the same underlying database technology.

| Store | Purpose | Primary writers | Primary readers |
| --- | --- | --- | --- |
| **Mock LMS Resource / Event Data Store** | Holds the seeded Mock LMS catalog and any related event-supporting data needed by the Mock LMS service | Fixture generator / seed capture process | Mock LMS Event Producer; LMS Resource APIs; usable in Mock LMS Demo UI |
| **Validated Workflow Actions Plan Store** | Stores validated abstract workflow plans for reuse across similar events | Orchestrator after Policy Rules validation | Orchestrator (long term: made available in Admin UI) |
| **Versioned Action Registry** | Stores the allowed service/action vocabulary, step types, and input/output contracts supplied to the Workflow Actions LLM | Architecture/config management process | Workflow Actions LLM Decision Service; Policy Rules Service; (long term: managed in Admin UI) |
| **Policy Store** | Stores deterministic policy rules, validation constraints, and routing restrictions | Policy/config management process | Policy Rules Service; (long term: managed in Admin UI) |
| **Workflow Action Plan Execution Logs** | Stores per-workflow and per-step execution traces, step inputs/outputs, confidence scores, rationale, and delivery outcomes for admin review | Orchestrator; LLM services; Policy Rules Service; Delivery Router | Orchestrator read API to make visible in Admin UI |
| **Idempotency Store** | Stores previously-seen event or execution identifiers so ingress and execution can reject or suppress duplicate work | Event Consumer; Orchestrator | Event Consumer; Orchestrator |
| **Mapping Template Storage (Mock LIF MDR)** | Stores JSONata mappings plus synthesis placeholders keyed by relevant source/target combinations | Orchestrator post-validation | Transformation Executor; Orchestrator; (long term: managed in Admin UI) |
| **Badge Template Storage** | Stores credential templates produced by Loop 1 so repeat events can skip regeneration | Orchestrator post-validation of data from Transformation Executor | Field Mapping LLM Decision Service; Transformation Executor; Orchestrator; (long term: managed in Admin UI) |
| **Delivery Targets Store** | Stores available delivery target definitions, configuration, and target-specific contract metadata | Architecture/config management process | Delivery Targets LLM Decision Service; Delivery Router; (long term: managed in Admin UI) |
| **Source Fetch Rules Store** | Stores the deterministic fetch profiles / context recipes used by the Context Builder per event type or step | Architecture/config management process | Context Builder; (long term: managed in Admin UI) |

The **Idempotency Store** and **Workflow Action Plan Execution Logs** may share the same physical database, but they should remain **separate logical stores or tables** because their lookup patterns, retention rules, and correctness requirements are different.

## 8. Boundary Rules To Preserve In Follow-up Docs

- The **Mock LMS** is split into at least two service boundaries: **Event Producer** and **LMS Resource APIs**.
- The **Admin UI** is a first-class POC component per ADR-0002 and must have a clear read path into workflow execution state, LLM confidence scores, rationale, and selected step inputs/outputs.
- The **Event Consumer** is intentionally thin. It is an ingress boundary, not the place where orchestration logic accumulates.
- The **Orchestrator** executes plans and exposes correlated execution state; it does not collapse back into a monolithic "do everything" service.
- The original single **LLM Decision Service** is no longer a useful boundary for design work. Follow-up docs should use the specialized services from ADRs 0007 and 0008.
- The **Context Builder** owns deterministic source-data fetching rules.
- The **Policy Rules Service** remains deterministic and separate from LLM reasoning.
- The **Delivery Router / Target Adapters** deliver validated payloads; they do not reinterpret business logic already decided upstream.
- The **MCP Client Layer** is currently deferred rather than treated as an active top-level POC component; see [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md).
