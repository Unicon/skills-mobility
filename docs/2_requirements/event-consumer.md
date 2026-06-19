# Event Consumer Requirements

Status: Draft
Date: 2026-06-19
Related: [POC Requirements](./poc-requirements.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Event Consumer Design](../3_design/event-consumer.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md)

## 1. Purpose

The Event Consumer is the workflow ingress boundary for the POC. It receives events from the bus, performs deterministic ingress checks, creates the initial workflow execution record, and hands the run to the Orchestrator.

It is intentionally thin. It should not accumulate orchestration logic, context-building logic, policy reasoning, mapping logic, or delivery behavior.

## 2. Responsibilities

The Event Consumer is responsible for:

- Receiving incoming events from the event bus
- Validating event-envelope structure
- Deriving or reading the event identity needed for ingress idempotency
- Enforcing primary event-level idempotency
- Creating the execution identifier and initial workflow record for a new run
- Handing the new run to the Orchestrator

The Event Consumer is not responsible for:

- Building context from source systems
- Choosing source APIs to fetch
- Generating workflow plans
- Validating plans or payloads as policy
- Selecting delivery targets
- Transforming payloads
- Delivering to downstream systems

## 3. Inputs and Outputs

### Inputs

- Event envelopes published to the POC event bus by the Mock LMS Event Producer

### Outputs

- A workflow start request to the Orchestrator for a new event
- An initial execution record for the workflow
- Idempotency decisions that either suppress duplicate work or allow a new run to begin

## 4. Functional Requirements

- **FR-EC-1** The Event Consumer SHALL accept events from the POC event bus.
- **FR-EC-2** The Event Consumer SHALL validate that the event envelope contains the fields required to identify the event and start a workflow.
- **FR-EC-3** The Event Consumer SHALL enforce primary event-level idempotency before creating a new workflow.
- **FR-EC-4** When an event is new, the Event Consumer SHALL create an execution identifier and an initial workflow record.
- **FR-EC-5** When an event is determined to be a duplicate, the Event Consumer SHALL suppress duplicate workflow creation.
- **FR-EC-6** The Event Consumer SHALL hand new workflow runs to the Orchestrator using a deterministic, machine-readable start request.
- **FR-EC-7** The Event Consumer SHALL record enough information to correlate the incoming event with the created workflow execution.
- **FR-EC-8** The Event Consumer SHALL remain independent of context-building, plan-generation, policy, transformation, and delivery logic.
- **FR-EC-9** The minimum required envelope fields for ingress are `metadata.event_name`, `metadata.event_id`, `metadata.correlation_id`, and `metadata.user_id`. For `course_completed` events, `metadata.context_id` is also required. For `skill_mastered` events, `body.learning_outcome_id` is also required. For `badge_awarded` events, `body.badge_id` is also required.
- **FR-EC-10** When envelope validation fails, the Event Consumer SHALL log a structured error including the raw envelope and validation details, write a rejection record to the idempotency store with status `rejected`, and not propagate the error as a retry-eligible exception. When validation fails because identity fields are missing and the business key cannot be derived, the rejection record SHALL use the raw `event_id` from the envelope as its store key; if `event_id` is also absent, a generated UUID SHALL be used.

## 5. Idempotency Requirements

- **FR-EC-11** The Event Consumer SHALL use stable event identity inputs from the received envelope plus any required deterministic derivation rules to decide whether the event has already produced a workflow execution. The stable event identity key is derived as follows:
  - `skill_mastered`: `event_name` + `user_id` + `learning_outcome_id`
  - `course_completed`: `event_name` + `user_id` + `context_id` (course)
  - `badge_awarded`: `event_name` + `user_id` + `badge_id`
- **FR-EC-12** The Event Consumer SHALL use a persistent idempotency record rather than in-memory process state as the source of truth for duplicate suppression.
- **FR-EC-13** The Event Consumer SHALL create the initial workflow state only after the event passes the idempotency check.

## 6. POC Constraints

- The Event Consumer may assume the upstream event source is the Mock LMS Event Producer.
- The Event Consumer does not need to solve production-scale throughput or multi-tenant isolation in the POC.
- The Event Consumer should favor deterministic, inspectable behavior over flexibility.
- Idempotency is keyed on stable business fields (`event_name` + `user_id` + object id), not on the per-delivery `event_id`. Re-triggering the same scenario for the same learner will be suppressed as a duplicate. The Mock LMS Reset action (FR-EP10) is the intended reset path for demo re-runs; as part of that reset it calls the Event Consumer to clear the relevant idempotency records before re-triggering (see FR-EC-23).

## 7. Local vs AWS Requirements

- **FR-EC-14** For local development, the Event Consumer SHALL expose an HTTP ingress endpoint (`POST /ingest`) that accepts the raw event envelope. The Mock LMS `LocalEmitter` delivers events to this endpoint when `EVENT_CONSUMER_URL` is configured, standing in for the EventBridge trigger.
- **FR-EC-15** For local development, the Event Consumer SHALL persist its idempotency decision and initial workflow record to a local inspectable store rather than relying only on transient process memory.
- **FR-EC-16** For local development before the Orchestrator exists, the Event Consumer SHALL support a stub or capture-mode Orchestrator handoff that records the exact workflow start request it would have sent downstream.
- **FR-EC-17** For the AWS-shaped deployment target, the Event Consumer SHALL consume events from the AWS event path and write its idempotency and initial workflow state to durable AWS-backed persistence.
- **FR-EC-18** For the AWS-shaped deployment target, the Event Consumer SHALL hand new workflow runs to the real Orchestrator integration rather than to a stub handoff capture.

## 8. Testability Requirements

- **FR-EC-19** A developer SHALL be able to trigger a test event through the Mock LMS UI and confirm that the Event Consumer received it.
- **FR-EC-20** A developer SHALL be able to determine, from inspectable artifacts, whether the Event Consumer suppressed the event as a duplicate or created a new workflow execution.
- **FR-EC-21** Before the Orchestrator exists, a developer SHALL be able to inspect the captured workflow start request that the Event Consumer attempted to hand off.
- **FR-EC-22** The minimum local inspection artifacts SHALL include structured logs plus persisted idempotency and execution records.
- **FR-EC-23** For local development, the Event Consumer SHALL expose a reset endpoint so that the Mock LMS Reset action can clear the relevant idempotency records before a demo re-run, enabling the same learner and event type to produce a new workflow execution.
