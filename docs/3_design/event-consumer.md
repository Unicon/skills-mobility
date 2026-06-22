# Event Consumer Design

Status: Draft
Date: 2026-06-19
Related: [Event Consumer Requirements](../2_requirements/event-consumer.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md)

## 1. Overview

The Event Consumer is a small ingress service or ingress module whose job is to turn a received event into either:

- a suppressed duplicate decision, or
- a new workflow start for the Orchestrator.

It should be designed as a deterministic boundary, not as a place where orchestration behavior grows.

## 2. Runtime Shape

The minimal logical flow is:

1. Receive an event from the event bus.
2. Parse and validate the envelope.
3. Determine the stable event identity used for ingress idempotency.
4. Check the idempotency store.
5. If the event is already known, suppress duplicate workflow creation.
6. If the event is new, create the execution identifier and initial workflow record.
7. Hand the workflow start request to the Orchestrator.

This aligns with ADR-0011's ingress responsibility split: event idempotency and workflow creation belong here; context assembly, planning, policy validation, and step execution do not.

## 3. Logical Modules

The Event Consumer lives at `services/event-consumer/` in the monorepo. It runs as a FastAPI service locally and deploys as a Lambda function triggered by EventBridge in AWS (see ADR-0015).

The initial implementation should stay small. The useful logical parts are:

- **Ingress adapter**: receives messages from the bus and converts them into the service's internal event-envelope shape
- **Envelope validator**: checks required structure and fields before workflow creation
- **Idempotency repository**: reads and writes the persistent idempotency record
- **Execution record creator**: creates the execution identifier and initial workflow state for new events
- **Orchestrator handoff client**: sends the deterministic workflow start request downstream

These can be separate modules inside one service; they do not need to become separate deployable services.

## 4. Data Responsibilities

The Event Consumer owns two pieces of write behavior:

- the ingress idempotency decision record
- the initial workflow execution record

It does not own long-running workflow state progression after handoff.

The `workflow_execution` record is needed even though the Event Consumer is thin. The idempotency record answers "have we already started a workflow for this event?" The workflow execution record answers "what workflow run did we create, and what is its initial state?" Keeping them separate makes duplicate suppression and workflow state inspection easier to reason about, and it gives developers something concrete to inspect even before the full Orchestrator exists.

The workflow start request to the Orchestrator contains the raw event envelope exactly as received, plus the execution identifier and initial workflow status created by the Event Consumer. The Event Consumer adds no interpretation or transformation to the event data; the Orchestrator reads what it needs directly from the envelope.

The minimum useful `workflow_execution` fields are:

- execution identifier
- source event identifier
- correlation identifier
- event type
- initial workflow status such as `created`, `handoff_captured`, or `handoff_sent`
- created timestamp

## 5. Idempotency Design

Ingress idempotency should be event-focused rather than step-focused.

The stable event identity key is derived deterministically from envelope fields:

| Event type | Identity key components |
|---|---|
| `skill_mastered` | `event_name` + `user_id` + `learning_outcome_id` |
| `course_completed` | `event_name` + `user_id` + `context_id` (course) |
| `badge_awarded` | `event_name` + `user_id` + `badge_id` |

The key is a deterministic canonical string combining these values. It is stable across repeated event delivery because it is derived from business keys, not from the per-delivery `event_id`.

The Event Consumer should:

- derive the stable event identity key from the envelope
- check whether that identity has already produced a workflow execution
- suppress duplicate workflow creation when a prior execution already exists
- write the new idempotency record and initial workflow record together closely enough that duplicate creation is avoided

The Orchestrator still needs retry-safe execution behavior, but that is a separate concern from ingress duplicate suppression.

For the AWS-backed implementation, the recommended persistence pattern is:

- DynamoDB table `ingress_idempotency` keyed by the stable event identity
- DynamoDB table `workflow_execution` holding the initial workflow record and later execution state
- a **conditional write** against `ingress_idempotency` rather than a read-then-write duplicate check
- a **DynamoDB transaction** that creates both the idempotency record and the initial workflow record when the event is new

Recommended fields in `ingress_idempotency` are:

- stable event identity
- execution identifier
- event type
- correlation identifier
- first-seen timestamp
- current ingress status

This keeps duplicate suppression atomic and inspectable.

## 6. Local vs AWS

The Event Consumer should preserve the same ingress contract in both environments, but the surrounding adapters and verification methods will differ.

### Local development shape

For local development:

- the Event Consumer runs as a FastAPI service at `services/event-consumer/`, exposing `POST /ingest`
- the Mock LMS `LocalEmitter` delivers events to this endpoint when `EVENT_CONSUMER_URL` is configured; without it, `LocalEmitter` captures in-process without forwarding (existing test behavior is unchanged)
- idempotency records and initial workflow records should be written to a local inspectable SQLite database
- if the Orchestrator does not exist yet, the handoff layer should run in **capture mode** rather than failing silently

SQLite is the recommended local store because it gives the POC:

- a persistent local file
- transactional writes
- a simple way to mirror the same logical split used in AWS
- straightforward inspection during manual testing

The local store should preserve the same logical split as AWS:

- one SQLite table for ingress idempotency decisions
- one SQLite table for workflow execution records

`Capture mode` means the Event Consumer writes the workflow start request it would have sent to the Orchestrator into a local SQLite `orchestrator_outbox` table. Each row holds the execution identifier, the raw event envelope as JSON, a created timestamp, and a `captured` flag. A developer inspects this table to confirm the correct handoff payload was produced.

The important point is that a developer can prove:

1. the event reached the Event Consumer,
2. the idempotency decision was made,
3. the initial execution record was created when appropriate,
4. and the downstream handoff payload was produced.

### AWS-shaped deployment target

For the AWS-shaped target:

- the input side should be the real AWS event path
- the Event Consumer should remain a small bus-triggered boundary
- idempotency records should be written to DynamoDB table `ingress_idempotency`
- initial workflow records should be written to DynamoDB table `workflow_execution`
- the handoff layer should call the real Orchestrator integration rather than capture mode

The recommended AWS sequence is:

1. receive the event from the AWS event path,
2. derive the stable event identity,
3. attempt a conditional write into `ingress_idempotency`,
4. create the initial workflow record in `workflow_execution`,
5. and then hand off to the Orchestrator.

When practical, steps 3 and 4 should be done in one DynamoDB transaction.

The exact AWS primitives can vary later; the design constraint is the boundary behavior, not the specific trigger implementation.

## 7. How To Test It

### Local manual test before the Orchestrator exists

The intended manual smoke test is:

1. Run the Mock LMS locally and run the Event Consumer in local mode.
2. Use the Mock LMS UI to trigger a supported event.
3. Confirm in the Mock LMS UI or emission feed that the event was emitted and note the correlation id or event id.
4. Check the Event Consumer structured logs for:
   - event receipt
   - idempotency decision
   - execution identifier creation when the event is new
5. Inspect the local idempotency record and initial execution record.
6. Inspect the local handoff capture artifact and confirm it contains the workflow start request that would have gone to the Orchestrator.

Before the Orchestrator exists, step 6 is the key proof that the Event Consumer did everything it was supposed to do.

### Local manual test after the Orchestrator exists

Once the Orchestrator exists, the same manual trigger path should still work, but the final check changes:

- instead of inspecting only a capture artifact, the developer should confirm that the real downstream handoff occurred
- the evidence can be an Orchestrator receipt log, a persisted workflow record created downstream, or another explicit ingestion artifact owned by the Orchestrator

### AWS verification

In the AWS-shaped environment, a developer or operator should verify:

- the event arrived through the AWS event path
- the Event Consumer emitted structured logs for receipt and idempotency decision
- durable idempotency and initial execution records were written
- the real Orchestrator handoff occurred

## 8. Failure Behavior

Envelope validation failures are permanent — retrying a malformed event will never succeed — so the Event Consumer must not propagate them as retry-eligible exceptions.

When an event fails envelope validation:

1. Log a structured error containing the raw envelope and the validation details.
2. Write a rejection record to the idempotency store with status `rejected`. This makes the failure inspectable and prevents the same malformed event from being re-processed if it is redelivered. The record is normally keyed by the stable business key; when validation fails because identity fields are missing and the business key cannot be derived, use the raw `event_id` from the envelope as the store key instead. If `event_id` is also absent, generate a UUID for the key.
3. Ack the event to the caller without raising an exception. For AWS Lambda + SQS, this means returning normally so the message is not returned to the queue.
4. For local HTTP (`POST /ingest`), return 422 Unprocessable Entity with the structured error body.

If writing the rejection record fails due to a transient infrastructure error, propagate that error so the delivery mechanism can retry. The distinction is: malformed payload → ack; infrastructure unavailability → retry.

## 9. Boundary Rules

- Do not fetch LMS source data here.
- Do not generate workflow plans here.
- Do not validate business policy here beyond envelope and ingress rules.
- Do not deliver downstream payloads here.
- Do keep the handoff to the Orchestrator explicit and machine-readable.
