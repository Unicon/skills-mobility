# Admin UI Requirements

Status: Draft
Date: 2026-06-25
Related: [Requirements overview](./README.md) · [Mock LMS UI](./mock-lms-ui.md) · [Orchestrator Requirements](./orchestrator.md) · [Event Consumer Requirements](./event-consumer.md) · [Design](../3_design/admin-ui.md) · [ADR-0002](../decisions/0002-frontend-architecture.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0015](../decisions/0015-orchestrator-execution-model.md) · [ADR-0018](../decisions/0018-admin-ui-frontend-stack.md)

## 1. Purpose

The **Admin UI** (`apps/admin`) is the POC's operability and observability surface. Where the [Mock LMS UI](./mock-lms-ui.md) is the *upstream* console — the presenter triggers an Action and watches the event emit — the Admin UI is its **downstream pair**: it makes the orchestration that the event drives **legible and inspectable** after the fact.

For a stakeholder demo, the presenter triggers a workflow in the Mock LMS, copies the run's `correlation_id` (Mock LMS [FR-UI8](./mock-lms-ui.md)), and follows that *same* workflow here — seeing how the Orchestrator planned and executed it.

**Two identifiers, deliberately distinct.** They are not the same value and serve different roles:

- **`correlation_id`** — stamped by the Mock LMS, **one per Action run**, and carried on every event that run emits ([Mock LMS design §4](../3_design/mock-lms.md)). It is the *demo-visible* id the presenter copies and the thread that ties an Action run to everything downstream.
- **`execution_id`** — minted by the Event Consumer when it accepts an event and creates the workflow record ([Event Consumer design §4](../3_design/event-consumer.md)); it is the *primary key* of **one** Orchestrator workflow run.

The relationship is **one-to-many, not one-to-one.** A Mock LMS Action can run for one learner *or all enrolled learners* (Mock LMS [FR-UI3](./mock-lms-ui.md)), and a bulk run emits one event per learner under a **single shared `correlation_id`** — each event becomes its own workflow execution. So one `correlation_id` resolves to a **correlation group of 1..N executions**, each with its own `execution_id`. The [correlation-id pivot](#4-functional-requirements) (FR-AU-8) resolves to that group: a single match opens the workflow directly; multiple matches open the list scoped to the group. Surfacing `correlation_id` on the read model so this resolution is possible is one of the prerequisites in [§5](#5-read-api-requirements-on-the-orchestrator).

The Admin UI exists to answer, per workflow:

- **What happened** — the workflow execution timeline and terminal outcome.
- **In what order, and how did each step fare** — per-step status, timing, inputs, and outputs.
- **Why** — the decision/gate logs and AI-agent reasoning the Orchestrator recorded (a deterministic stub in Phase 1; the seam for real LLM reasoning later).
- **For which event** — correlation tracing back to the originating Mock LMS Action.

This is an **operational/observability** surface, not an administrative control panel. It reads and renders what the Orchestrator already produces; it does not mutate workflow state, configuration, or the Orchestrator's own dev controls (see [§8](#8-out-of-scope)).

## 2. Orchestrator as data source and the polling model

The **Orchestrator is the backend that powers the Admin UI.** Its execution records are the only data the Admin UI displays. Per [ADR-0014](../decisions/0014-poc-storage-strategy.md) the Orchestrator persists execution state to a local SQLite store and exposes a read API over it; the Admin UI is a client of that read API.

Two facts about the current Orchestrator anchor this spec:

- The Orchestrator **returns the full per-step outcome of the end-to-end workflow synchronously in the `POST /run-workflow` response** (the **execution read model** — the Orchestrator's execution-logs metadata; its concrete type name is still being settled in the Orchestrator, so this doc refers to it generically rather than by class name). This synchronous per-step outcome is the most certain data available and is the canonical shape the Admin UI renders. (In Phase 1 the per-step work is stubbed, but that is a property of the step implementations, not of the read model the Admin UI consumes — see [Orchestrator design](../3_design/orchestrator.md).)
- The Orchestrator **also persists execution to SQLite** and serves it back via `GET /executions/{execution_id}`. The Admin UI reads from this persisted store rather than from the trigger response, because the presenter inspects workflows *after* they run, from a different app.

- **FR-AU-1** The Admin UI SHALL treat the Orchestrator's read API over its execution store as its sole data source. It SHALL NOT compute, infer, or synthesize workflow state the Orchestrator does not provide.
- **FR-AU-2** For the MVP, the Admin UI SHALL obtain fresh data by **polling** the Orchestrator read API. A live in-flight workflow SHALL be reflected by periodic re-fetch, not by a push channel.
- **FR-AU-3** The Admin UI SHALL consume execution data through a transport-agnostic subscription seam so that polling can later be replaced by a **server-push** transport without changing the views (see [design §4](../3_design/admin-ui.md)). **SSE** is the intended upgrade — server→client only, which suits this read-only surface; the trigger is the Orchestrator gaining asynchronous, per-step-progress execution ([ADR-0015](../decisions/0015-orchestrator-execution-model.md)). The push transport itself is **out of scope** for the MVP (see [§8](#8-out-of-scope)).

## 3. Information architecture

The Admin UI presents data **per-event / per-workflow**, not as one undifferentiated global stream ([ADR-0002](../decisions/0002-frontend-architecture.md)). It has three levels:

1. **Workflow list** — the entry point: recent executions with correlation id, event type, status, timing, and step progress. Includes a **correlation-id pivot**: the presenter pastes the id copied from the Mock LMS and lands on the matching workflow — or, for a bulk Action run, the list scoped to that correlation group (one row per learner's execution).
2. **Per-workflow detail** — one execution's timeline: header (status, ids, event type, plan id, copyable correlation id, final outcome), the **gate decision** (decision + rationale + confidence), and the ordered **step timeline**.
3. **Per-step decision/reasoning view** — selecting a step reveals its detail: action, status, attempt, timing, inputs, raw output JSON, and any error. For a step that is itself an LLM Decision Service, this view also shows that step's own decision/confidence/rationale. Presented as master-detail **within** the per-workflow view, not as a separate page.

- **FR-AU-4** The Admin UI SHALL present workflows individually (per-event / per-workflow), and SHALL NOT present orchestration as a single global, undifferentiated event stream.
- **FR-AU-5** The three levels above SHALL be navigable: list → workflow detail → step detail, with step detail rendered in context of its workflow.

## 4. Functional requirements

### Workflow list

- **FR-AU-6** The Admin UI SHALL display a list of recent workflow executions, each showing at minimum: correlation id, event type, status, a timestamp, and step progress (e.g. completed/total or terminal outcome).
- **FR-AU-7** Selecting a workflow from the list SHALL open its per-workflow detail view.
- **FR-AU-8 (Correlation-id pivot):** The Admin UI SHALL let the operator enter a `correlation_id` (copied from the Mock LMS) and resolve it to its **correlation group** of executions (Mock LMS Actions are one-to-many — see [§1](#1-purpose)). When the group has exactly one execution the UI SHALL open that workflow directly; when it has several (a bulk Action run) the UI SHALL show the workflow list scoped to that group; when it has none the UI SHALL show a clear empty state (see FR-AU-22). This is the cross-app pivot that pairs with Mock LMS [FR-UI8](./mock-lms-ui.md).

### Per-workflow detail

- **FR-AU-9** The per-workflow view SHALL show the execution header: `execution_id`, `correlation_id` (copyable), `event_type`, workflow `status`, `plan_id`, and the final `result`/outcome when present.
- **FR-AU-10** The per-workflow view SHALL render the ordered step timeline, each entry showing the `action_id`, step `status`, and timing.
- **FR-AU-11 (Decision / AI reasoning):** The per-workflow view SHALL surface the workflow's recorded **decision artifacts** as its reasoning log. In Phase 1 the only artifact is the pre-target **gate decision** (`decision`, `confidence`, `rationale`), a deterministic stub. The view SHALL render it as a **collection** rather than a single fixed field, so the surface grows with the orchestration model without a redesign: the target audit set ([ADR-0011](../decisions/0011-orchestration-runtime-technology.md), [ADR-0010](../decisions/0010-llm-model-access-strategy.md)) adds the selected delivery targets, the delivery-phase plan with its confidence/rationale, policy-validation results, per-decision model/prompt metadata, and delivery results. Per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md), Workflow Actions is **two-stage**, so a continue-path execution produces *two* Workflow Actions artifacts (pre-target gate + delivery-phase plan), not one — the collection SHALL accommodate that. The number of artifacts is therefore orchestration-model-dependent; see the cross-doc note in [§9](#9-open-questions--prerequisites).

### Per-step detail

- **FR-AU-12** Selecting a step SHALL reveal that step's detail: `action_id`, `status`, `attempt`, `started_at`/`finished_at`, the resolved **inputs** that produced it, the step's raw `output`, and `error` when present. When the step is itself an **LLM Decision Service** (e.g. delivery-target selection, field mapping/synthesis), its detail SHALL also surface that step's `decision`, `confidence`, and `rationale` — the same reasoning shape FR-AU-11 shows at the workflow level, presented at the step that produced it. (In Phase 1 these steps are deterministic stubs, so that surface is empty/stubbed until the real LLM services land.) The current step read model carries `output`/`error`/timing but **not** inputs or per-step reasoning (see [design §3](../3_design/admin-ui.md)); exposing resolved step inputs — inline for small payloads, or an artifact reference for large ones — is a read-API addition tracked in [§5](#5-read-api-requirements-on-the-orchestrator) (FR-AU-18a).
- **FR-AU-13 (Raw payload):** Step output, the gate decision, and the final result SHALL each be inspectable as **raw JSON**, using a shared JSON/envelope viewer consistent with the Mock LMS UI.

### Tracing and refresh

- **FR-AU-14 (Copyable ids):** `correlation_id` and `execution_id` SHALL be copyable wherever shown, so the operator can cross-reference the Mock LMS emission and the Orchestrator record.
- **FR-AU-15 (Polling refresh):** While viewing a non-terminal workflow, the Admin UI SHALL periodically re-fetch and update the view so an in-progress run advances without a manual reload. It SHALL stop polling once the workflow reaches a terminal status (`completed`/`failed`).

### Failure, empty, and edge states

- **FR-AU-22 (Non-happy-path states):** The Admin UI SHALL present clear, non-blank states for at least: an empty workflow list (no executions yet); a `correlation_id` or `execution_id` that resolves to **no** match; a `correlation_id` that resolves to **many** (the scoped-group case, FR-AU-8); the read API being unreachable or returning an error; and a malformed or unexpectedly large JSON payload in the viewer (it SHALL degrade gracefully, not crash the view). A failed copy-to-clipboard SHALL fail visibly rather than silently.
- **FR-AU-23 (Failed-workflow legibility):** A workflow in `failed` status SHALL be distinguishable in the list and SHALL surface the failing step and its `error` in the detail view; the Admin UI renders the failure the Orchestrator recorded — it does not retry or recover.

## 5. Read-API requirements on the Orchestrator

The Orchestrator today exposes only `GET /executions/{execution_id}` and does not surface a list, a correlation-id lookup, or `correlation_id`/timestamps in its read model. Per Orchestrator [FR-OR-19](./orchestrator.md), a finished Admin UI read API is explicitly out of scope of the Orchestrator's first slice. This section states the read-API surface the Admin UI **requires**; the not-yet-implemented additions are tracked on the Orchestrator side in [issue #28](https://github.com/Unicon/skills-mobility/issues/28) (G1–G7), where **G1–G4 are MVP-blocking** (the list and correlation pivot need them) and G3/G4 are already being added in the Orchestrator PR (#22). The mapping: FR-AU-16 → G1, FR-AU-17 → G2, FR-AU-18 → G3/G4, FR-AU-18a → G5, FR-AU-18b → G7.

- **FR-AU-16** The Orchestrator SHALL expose a **list endpoint** returning executions with the fields FR-AU-6 needs (correlation id, event type, status, a timestamp, step progress), ordered by `updated_at` descending and capped at a default `limit` (e.g. 50) overridable by a `limit` query param. "Recent" means this most-recent-N window; the single demo user and seeded data keep the volume small. Pagination and server-side filtering (by status, event type, or time window) are **deferred** — the `GET /executions?limit=…` ordered shape leaves room to add a cursor later without breaking the contract. *(Not yet implemented.)*
- **FR-AU-17** The Orchestrator SHALL expose a way to **resolve a `correlation_id` to its correlation group** — the set of executions sharing that id (a lookup or a `correlation_id` filter on the list). Because a bulk Mock LMS Action run fans out to many executions under one `correlation_id`, this SHALL return a list of 0..N executions, not a single record, so FR-AU-8's pivot is backed by data. *(Not yet implemented.)*
- **FR-AU-18** The Orchestrator's execution read model SHALL surface `correlation_id` and workflow-level timestamps (`created_at`/`updated_at`), which it persists but does not currently return. *(Not yet implemented.)*
- **FR-AU-18a** The read model SHALL expose each step's **resolved inputs** (FR-AU-12) — inline for small payloads or as an artifact reference for large ones. *(Not yet implemented; `StepResult` carries no inputs today.)*
- **FR-AU-18b** As the orchestration matures (FR-AU-11), the read model SHALL surface the full set of **decision artifacts** beyond `gate_decision` — selected delivery targets, the delivery-phase plan with confidence/rationale, policy-validation results, per-decision model/prompt metadata, and delivery results — as a collection on the execution read model. That metadata SHALL make the LLM-vs-fallback distinction explicit rather than leaving it implicit: `decision_source` (`"llm"` | `"deterministic_fallback"`, renamed from `plan_source` to avoid colliding with issue #128's `output_source`) on each `DecisionArtifact` and the executed plan, and — once their own backend issues land — `output_source` (per-step, issue #128) and `provider`/`injection_findings` (per-service, issue #129). A target selection that violates the issuer-inclusion design premise is *not* surfaced as a dedicated field (`issuer_omitted_from_selection` was added then dropped) — it stays visible via the Orchestrator's own error logging, with general decision-content surfacing tracked separately as issue #133. *(Partially implemented; Phase 1 surfaces `gate_decision`/`delivery_targets`/`workflow_actions_plan` today with `decision_source` populated — `output_source`/`provider`/`injection_findings` are tracked separately and may land later or not at all.)*
- **FR-AU-19** The existing `GET /executions/{execution_id}` execution read model (status, gate decision, plan id, per-step results, final result) is the per-workflow and per-step data contract for [§3](#3-information-architecture) levels 2–3, extended by FR-AU-18/18a/18b.

## 6. User and auth

- **FR-AU-20** A single **demo user** signs in and has full read capability across the Admin UI. There is no separate role model — for the POC the distinction adds no functionality ([ADR-0002](../decisions/0002-frontend-architecture.md)).
- **FR-AU-21** Auth is handled at the **CloudFront layer** per [ADR-0002](../decisions/0002-frontend-architecture.md) (Cognito was considered and not chosen); no secrets in the repo. Auth is kept behind a single boundary so the issuer could change cheaply if that ever changes.

## 7. Non-functional

- **NFR-AU-1 (Lightweight):** React SPA deployed as static assets on S3 + CloudFront, the same model as `apps/mock-lms` ([ADR-0002](../decisions/0002-frontend-architecture.md)).
- **NFR-AU-2 (Freshness):** With polling, an in-progress workflow SHOULD reflect new state within a few seconds of the operator opening or holding the view. Exact interval is a design choice ([design §4](../3_design/admin-ui.md)).
- **NFR-AU-3 (Legible):** Every workflow, step, decision, and result is inspectable as raw JSON and tied to copyable ids.
- **NFR-AU-4 (Consistent identity):** The Admin UI SHALL re-express the Mock LMS aesthetic through shared design tokens rather than inventing a separate visual identity ([ADR-0018](../decisions/0018-admin-ui-frontend-stack.md)).
- **NFR-AU-5 (Accessibility):** Interactive surfaces SHALL be keyboard-operable, the step-detail panel/dialog SHALL trap and restore focus (Radix primitives provide this — [ADR-0018](../decisions/0018-admin-ui-frontend-stack.md)), copyable ids SHALL be real buttons rather than clickable `span`s, and animations SHALL respect `prefers-reduced-motion`. This applies equally to primitives extracted into `packages/ui`: the Mock LMS copyable-id markup SHALL NOT be lifted into the shared package unchanged.
- **NFR-AU-6 (Data handling — POC):** The Admin UI renders **demo data only** and SHALL NOT hold secrets. Because raw JSON and rationale strings may contain learner-data fragments ([ADR-0010](../decisions/0010-llm-model-access-strategy.md)), there is no retention beyond what the Orchestrator store holds, and no learner-data redaction or row-level access control in the POC. Introducing **real** learner data is the explicit trigger to add redaction and access control before that point; the Admin UI SHALL NOT be pointed at real learner data until then.

## 8. Out of scope

- **Real-time push.** Pub/sub, SSE, or WebSocket freshness — polling only for the MVP (FR-AU-2/3).
- **Configuration and admin mutations.** The Admin UI does not mutate workflow state, plans, or settings. In particular it does **not** expose the Orchestrator's developer controls (`POST /admin/plan-lookup`, `DELETE /admin/plans/{id}`); those are dev affordances, not Admin UI features.
- **Anything not backed by Orchestrator data.** No derived analytics, no cross-workflow aggregation, no editing of source events or LMS data.
- **The Mock LMS's upstream concerns** — course browsing, Action triggering, and the emission feed live in `apps/mock-lms`.
- **Replaying or re-running workflows** from the Admin UI.

## 9. Open questions / prerequisites

- **Confirm exactly what is persisted per step at runtime.** The Orchestrator code persists each step's `output` inline (`workflow_step_execution.output_json`) and returns it from `GET /executions/{id}`, so per-step output appears to be durably stored, not merely returned in the trigger response. This was not exercised during Orchestrator PR review and SHOULD be verified against a real run before the Admin UI relies on it — confirming what is durably stored versus only returned in the synchronous `POST /run-workflow` response.
- **Read-API prerequisites.** FR-AU-16, FR-AU-17, and FR-AU-18 require Orchestrator read-API additions (list endpoint, correlation-id lookup, and surfacing `correlation_id`/timestamps) that do not exist yet. These are prerequisites for the workflow list and the correlation-id pivot, and should be sequenced before or alongside the Admin UI build.
- **Execution-id vs correlation-id mapping.** The `execution_id` is minted by the Event Consumer; the `correlation_id` originates in the Mock LMS. The pivot depends on the Orchestrator persisting and exposing the link (the store keeps `correlation_id`; the read model must expose it). Because a bulk Action run shares one `correlation_id` across many executions ([§1](#1-purpose)), the lookup must return a group, not a single record (FR-AU-17).
- **Cross-doc items are tracked as GitHub issues**, not in this doc: the Orchestrator read-API additions ([#28](https://github.com/Unicon/skills-mobility/issues/28), G1–G7); the single- vs two-stage Workflow Actions wording across ADR-0010/0013/0015 ([#29](https://github.com/Unicon/skills-mobility/issues/29)); the ADR-governance/status cleanup ([#30](https://github.com/Unicon/skills-mobility/issues/30)); and the stale Mock LMS live-feed requirement, FR-UI6 ([#31](https://github.com/Unicon/skills-mobility/issues/31)).
