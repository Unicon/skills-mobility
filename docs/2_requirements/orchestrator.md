# Orchestrator Requirements

Status: Draft
Date: 2026-06-23
Related: [Requirements overview](./README.md) · [Phase 1 POC Slice](./phase-1-poc-slice.md) · [Target POC Requirements](./target-poc-requirements.md) · [Design](../3_design/orchestrator.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0015](../decisions/0015-orchestrator-execution-model.md)

## 1. Purpose

The **Orchestrator** is the workflow execution runtime for the POC. It receives workflow start requests from the **Event Consumer**, assembles the execution context needed to plan and run the workflow, executes approved steps, and records the correlated execution trail.

For **Phase 1**, the Orchestrator should already use the same general plan-executor boundary intended for the target POC, even though several decision and transformation steps are satisfied by deterministic stubs rather than by their final LLM-backed services. The goal is to keep the Phase 1 slice small without discarding the workflow structure the later POC will need.

## 2. Responsibilities

The Orchestrator is responsible for:

- Accepting a deterministic workflow start request from the Event Consumer
- Persisting workflow-level and step-level execution state
- Invoking the Context Builder and making the returned context bundle, or a durable reference to it, available to later steps
- Obtaining a Workflow Actions pre-target decision and a delivery-phase plan through defined planner interfaces
- Executing the defined Phase 1 step set and, in later phases, the approved orchestration action set
- Passing step outputs forward through the execution context
- Invoking downstream services such as the LearnCard Profile Resolver and Delivery Router
- Recording enough execution log metadata for inspection, debugging, and later Admin UI use

The Orchestrator is not responsible for:

- Event-envelope validation or ingress idempotency
- Choosing which LMS source APIs the Context Builder should call
- Owning vendor-specific LearnCard or SmartResume delivery mechanics
- Embedding transformation, routing, or policy logic directly into the executor once those services exist

## 3. Inputs and Outputs

### Inputs

- Workflow start requests from the Event Consumer containing at minimum the raw event envelope and the `execution_id`
- Step results returned by invoked downstream services

### Outputs

- Invocations to the Context Builder, Workflow Actions pre-target boundary, Delivery Targets boundary, Workflow Actions delivery-phase boundary, transformation boundary, LearnCard Profile Resolver, and Delivery Router
- Persisted workflow and step execution records
- A final workflow outcome for the run
- Correlated execution log metadata owned by the Orchestrator

## 4. Phase 1 Scope

For **Phase 1**, the Orchestrator only needs to support the `skill_mastered` and `course_completed` happy paths.

The required Phase 1 flow is:

1. Receive the workflow start request from the Event Consumer.
2. Invoke the Context Builder with the raw event.
3. Invoke a deterministic stub of the first **Workflow Actions** call to decide whether the workflow terminates early or proceeds to delivery-target selection.
4. Execute a stub **Delivery Targets** step that selects LearnCard issuance and LearnCard wallet delivery.
5. Invoke a deterministic stub of the second **Workflow Actions** call to return the delivery-phase plan for the selected targets.
6. Invoke the **LearnCard Profile Resolver** and store the returned `profileId` and DID in execution context.
7. Execute a first transformation pass for LearnCard issuance using the same three service seams the full POC will later use:
   - a stub **Field Mapping** step,
   - a stub **Field Synthesis** step,
   - and a deterministic **Translation Executor** step that performs the minimum mapping needed to produce the LearnCard Issuer input payload.
8. Send that payload to the **Delivery Router**, which invokes the LearnCard Issuer Adapter and returns the issued badge.
9. Execute a second transformation pass for LearnCard wallet delivery using the same relevant transformation service seams:
   - a stub **Field Mapping** step,
   - and a deterministic **Translation Executor** step that performs the minimum mapping needed to produce the LearnCard Wallet input payload.
10. Send that payload to the **Delivery Router**, which invokes the LearnCard Wallet Adapter and returns the delivery result.

Phase 1 does not require the final LLM-backed decision services or the full target transformation pipeline to be implemented as real runtime dependencies. It does require preserving their invocation seams so the Orchestrator does not collapse into a permanent one-off flow.

## 5. Functional Requirements

- **FR-OR-1** The Orchestrator SHALL accept a deterministic workflow start request from the Event Consumer containing at minimum the `execution_id`, `event_id`, and `correlation_id` as explicit fields alongside the raw source event envelope.
- **FR-OR-2** The Orchestrator SHALL create or update a persistent workflow execution record for each started run and SHALL maintain workflow status transitions through to a terminal outcome.
- **FR-OR-3** The Orchestrator SHALL invoke the Context Builder after receiving the workflow start request and SHALL make the returned context bundle, or a durable reference to it, available to later orchestration steps. It SHALL NOT require duplicating the full bundle into every step record.
- **FR-OR-4** The Orchestrator SHALL obtain a Workflow Actions pre-target decision and a delivery-phase plan through defined planner interfaces rather than hard-coding the full orchestration path directly in the workflow-start handler.
- **FR-OR-5** For Phase 1, those planner interfaces MAY be satisfied by deterministic stub implementations, but the returned artifacts SHALL still use the intended target-PoC shapes: a pre-target Workflow Actions decision artifact and a delivery-phase Workflow Actions plan artifact.
- **FR-OR-6** For Phase 1, the Orchestrator SHALL execute only the defined Phase 1 orchestration step set described in this document.
- **FR-OR-7** The Orchestrator SHALL pass outputs from earlier steps to later steps through explicit execution-context data or durable artifact references rather than relying on hidden process-local coupling.
- **FR-OR-8** The Orchestrator SHALL persist step-level status, attempt count, timing, and result details for each executed step.
- **FR-OR-9** For Phase 1, the Orchestrator SHALL support the `skill_mastered` and `course_completed` event types.
- **FR-OR-10** For Phase 1, the first Workflow Actions stub SHALL determine whether the workflow terminates before delivery-target selection or proceeds to Delivery Targets. For the supported happy-path events in this document, it SHALL proceed.
- **FR-OR-11** For Phase 1, the Delivery Targets stub SHALL return LearnCard issuance and LearnCard wallet delivery as the selected targets.
- **FR-OR-12** For Phase 1, the deterministic delivery-phase plan returned by the second Workflow Actions stub SHALL include at minimum:
  - LearnCard profile resolution,
  - issuer-payload preparation,
  - LearnCard issuance,
  - wallet-payload preparation,
  - and LearnCard wallet delivery.
- **FR-OR-13** The Orchestrator SHALL invoke the LearnCard Profile Resolver before any LearnCard issuance or wallet delivery action that requires a resolved LearnCard identity, and SHALL store the returned `profileId` and DID in the execution context for downstream steps.
- **FR-OR-14** For Phase 1, the Orchestrator SHALL preserve the future transformation-service seam by representing issuer-payload preparation as explicit Field Mapping, Field Synthesis, and Translation Executor steps even when the first two are no-op stubs.
- **FR-OR-15** For Phase 1, the Orchestrator SHALL preserve the future transformation-service seam by representing wallet-payload preparation as explicit Field Mapping and Translation Executor steps, with Field Synthesis included only when the payload phase actually requires it.
- **FR-OR-16** For Phase 1, the issuer-side Translation Executor stub SHALL construct the minimum Open Badges 3.0 input payload required by the LearnCard Issuer Adapter from the source context plus the resolved LearnCard DID, embedding that DID in `credentialSubject.id`.
- **FR-OR-17** For Phase 1, the wallet-side Translation Executor stub SHALL construct the minimum payload required by the LearnCard Wallet Adapter from the issued badge plus the resolved LearnCard `profileId`.
- **FR-OR-18** The Orchestrator SHALL invoke the Delivery Router for `issue_learncard_badge` and `deliver_to_learncard_wallet` as separate delivery actions and SHALL correlate both results to the same workflow execution.
- **FR-OR-19** The Orchestrator SHALL own the correlated execution log metadata for the workflow. For Phase 1, this may be a minimal inspectable execution record and step log rather than the full Admin UI read model.

## 6. Validation and Audit Requirements

- **FR-OR-20** The Orchestrator SHALL record the pre-target gate decision in execution log metadata for each execution. It SHALL persist the delivery-phase plan used for an execution so a developer can inspect the decision path and, when applicable, the plan that was run. It SHALL NOT perform reusable-plan lookup for the pre-target gate.
- **FR-OR-21** The Orchestrator SHALL record structured execution log metadata for step inputs, outputs, and failures in a form that allows a developer to reconstruct the path taken through the workflow. Large context or payload artifacts MAY be stored once and referenced from step records rather than duplicated.
- **FR-OR-22** Step result envelopes SHALL use typed envelope fields and allow step-specific opaque JSON payloads or artifact references rather than requiring fully modeled Pydantic objects for every step result.
- **FR-OR-23** For the target POC, when probabilistic planning or transformation services are in use, the Orchestrator SHALL submit their outputs to deterministic policy validation before executing downstream side effects.
- **FR-OR-24** For Phase 1, a standalone Policy Rules runtime is not required for the happy path because the planning, routing, and transformation artifacts are deterministic stubs rather than live probabilistic outputs.

## 7. Local vs AWS Requirements

- **FR-OR-25** For local development, the Orchestrator SHALL expose an HTTP start endpoint that the local Event Consumer can call instead of publishing to SQS.
- **FR-OR-26** For local development, the Orchestrator SHALL persist workflow and step execution records to an inspectable SQLite-backed store, consistent with ADR-0014.
- **FR-OR-27** For local development, the Orchestrator MAY call downstream components either through `localhost` HTTP endpoints or direct in-process adapters, but it SHALL preserve the same logical request/response contracts it will use in AWS.
- **FR-OR-28** For local development and Workflow Actions testing, the Orchestrator SHALL provide a control mechanism, such as an API, to enable or disable reusable delivery-phase plan lookup without code changes.
- **FR-OR-29** Stored delivery-phase plans SHALL remain available until explicitly deleted. The Orchestrator MAY provide an API or administrative mechanism to delete stored plans when regeneration is desired, but automatic version-based invalidation is not required.
- **FR-OR-30** For the AWS-shaped deployment target, the Orchestrator SHALL follow the queue-driven worker model from ADR-0015: a planner worker and an executor worker, each hosted as Lambda and connected by SQS.
- **FR-OR-31** For the AWS-shaped deployment target, the Orchestrator SHALL persist operational execution state to DynamoDB, using out-of-line artifact storage and references when context bundles or payloads are too large or awkward to store inline.
- **FR-OR-32** For the intended AWS deployment, the Orchestrator SHALL be able to invoke the Context Builder, Workflow Actions pre-target boundary, Delivery Targets boundary, Workflow Actions delivery-phase boundary, LearnCard Profile Resolver, transformation boundary, and Delivery Router as separate Lambda-backed service boundaries without changing the logical plan or step contracts used locally.
- **FR-OR-33** For the AWS-shaped deployment target, the queue handoff between Orchestrator workers SHALL carry execution identifiers and ready-step metadata, not full copies of large context bundles or large step payloads.

## 8. Out of Scope

The initial Orchestrator does not need to provide:

- arbitrary replanning after the delivery-phase plan has already begun execution,
- human review waits,
- multi-day workflow suspension,
- general-purpose workflow authoring,
- cross-target fan-out beyond the Phase 1 LearnCard path,
- or a finished Admin UI read API in the first implementation slice.
