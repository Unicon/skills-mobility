# 0015. Event Consumer and Orchestrator Worker Execution Model

- Status: Accepted
- Date: 2026-06-19
- Related: [ADR-0011](./0011-orchestration-runtime-technology.md) · [ADR-0014](./0014-poc-storage-strategy.md) · [Event Consumer Design](../3_design/event-consumer.md)

## Context

ADR-0011 defined a project-internal orchestration service using a queue-driven model with distinct worker roles: an ingress component (the Event Consumer), a planner worker, and an executor worker. ADR-0014 resolved storage (DynamoDB + SQLite locally). The remaining open question is what deployment primitive should host each worker and how the workers connect.

Two practical concerns were raised:

1. Is Lambda memory sufficient for the Orchestrator's worker roles?
2. Is Lambda's 15-minute execution limit a risk for a component that may orchestrate multiple LLM calls?

## Decision

**Lambda + SQS is the deployment model for both the Event Consumer and the Orchestrator workers.**

- The Event Consumer deploys as a Lambda function triggered by EventBridge.
- The Orchestrator planner worker and executor worker each deploy as SQS-triggered Lambda functions.
- SQS queues connect the workers. The Event Consumer hands off to the Orchestrator by publishing the raw event envelope to the Orchestrator's SQS queue.

For local development:
- The Event Consumer runs as a FastAPI service (`POST /ingest` stands in for the Lambda handler).
- When the Orchestrator does not yet exist, handoff is captured in a SQLite `orchestrator_outbox` table (capture mode).
- When the Orchestrator exists locally, handoff is an HTTP POST to its local endpoint.

## Is Lambda Memory Sufficient?

Yes. Lambda supports up to 10 GB of memory. Text-based orchestration — even with large LLM prompts and context payloads — rarely exceeds a few hundred MB. Memory is not a constraint for any worker role in this architecture.

## Is the 15-Minute Limit a Risk?

No, for the POC. The queue-driven model keeps each Lambda invocation bounded to a single unit of work:

| Worker | What one invocation does | Expected duration |
|---|---|---|
| Event Consumer | Envelope validation + idempotency check + one write | Milliseconds |
| Planner | Context fetch + one Workflow Actions LLM call + Policy Rules validation | Seconds to low minutes |
| Executor | Advance one step, persist result | Seconds (per LLM or delivery call) |

The planner invocation is the longest expected step. Under ADR-0011's single-plan model, it makes one LLM call followed by deterministic validation. For POC scenarios this should complete well within 15 minutes.

If a future step approaches the limit, the step's adapter can be decomposed or moved to a Fargate task. That is a local change to that adapter, not a redesign of the execution model.

## Handoff Payload

The Event Consumer sends the raw event envelope to the Orchestrator exactly as received — no transformation, no interpretation. The Orchestrator reads what it needs from the envelope at planning time. Alongside the envelope, the message includes the execution identifier created by the Event Consumer so the Orchestrator can correlate its work back to the ingress record.

## Why Not a Long-Running Container or Service?

- The POC has low event volume; a long-running container would spend most of its time idle.
- Lambda scales to zero between events, matching expected POC usage patterns.
- The queue-driven model already treats each worker invocation as stateless — a Lambda invocation is exactly that model realized.
- A Fargate service adds operational complexity (task definitions, cluster, service configuration) without benefit at POC scale.

## Why Not Step Functions (Again)?

ADR-0011 already ruled out Step Functions as the primary orchestration engine because it cannot execute a runtime-generated plan as generated. That conclusion is unchanged. Lambda + SQS provides the same serverless primitives without requiring the plan to be expressed in Amazon States Language.

## Local Development Equivalents

| AWS primitive | Local equivalent |
|---|---|
| EventBridge trigger → Lambda (Event Consumer) | Mock LMS `LocalEmitter` HTTP POST to `POST /ingest` when `EVENT_CONSUMER_URL` is set |
| SQS message (Event Consumer → Orchestrator) | SQLite `orchestrator_outbox` table (capture mode) or HTTP POST to Orchestrator local endpoint |
| SQS-triggered Lambda (Orchestrator workers) | FastAPI request handler |

## Consequences

### Positive

- No new infrastructure beyond what the POC already requires (Lambda, SQS, DynamoDB from ADR-0014).
- Each worker invocation is stateless and independently testable.
- Local dev equivalents are lightweight (FastAPI + SQLite); no Lambda runtime needed locally.
- SQS provides natural backpressure and retry semantics without additional plumbing.

### Negative

- Cold starts between events (acceptable for POC usage patterns and event volumes).
- SQS visibility timeout and retry configuration must be set correctly for each queue to avoid double-processing.
- Any step that genuinely approaches the 15-minute Lambda limit requires decomposition (unlikely in POC).

### Revisit Triggers

- A step consistently approaches the 15-minute Lambda limit.
- The POC introduces long-running workflows requiring human review or multi-day wait steps.
- A durable workflow platform (e.g., Temporal, per ADR-0011) is adopted, changing the execution host for orchestrator workers.

## References

- [ADR-0011: Orchestration Runtime Technology](./0011-orchestration-runtime-technology.md)
- [ADR-0014: POC Storage Strategy](./0014-poc-storage-strategy.md)
- [Event Consumer Design](../3_design/event-consumer.md)
- [AWS Lambda quotas — function timeout and memory](https://docs.aws.amazon.com/lambda/latest/dg/gettingstarted-limits.html)
