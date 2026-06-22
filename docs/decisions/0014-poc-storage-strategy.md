# ADR-0014: POC Storage Strategy

- Status: Accepted
- Date: 2026-06-19
- Related: [ADR-0003](./0003-programming-language.md) · [ADR-0009](./0009-workflow-actions-orchestration-model.md) · [ADR-0011](./0011-orchestration-runtime-technology.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md)

## Context

The storage strategy needs to distinguish between:

- what is useful to stand up immediately in Phase 1 (the no-LLM end-to-end slice),
- what should exist by the end of the POC,
- and which logical stores should remain separate even when they share the same underlying technology.

The POC Component Boundary Matrix identifies ten important **logical stores**:

- Mock LMS Resource / Event Data Store
- Validated Workflow Actions Plan Store
- Versioned Action Registry
- Policy Store
- Workflow Action Plan Execution Logs
- Idempotency Store
- Mapping Template Storage
- Badge Template Storage
- Delivery Targets Store
- Source Fetch Rules Store

Those are intentionally described as **logical stores** rather than as immediately separate infrastructure products. Some are operational state, some are seeded mock data, some are versioned configuration, and some are reusable artifacts produced by LLM-driven or deterministic flows.

ADR-0011 also leaves an open implementation question: what concrete persistence backend should hold workflow state, reusable artifacts, and audit records in the POC.

## Decision

The POC will use the following storage strategy:

1. **DynamoDB is the primary AWS-backed operational persistence technology** for low-latency workflow state, idempotency, execution logs, and reusable artifact metadata.
2. **S3 is the companion AWS store for large artifacts or out-of-line payloads** when generated plans, mappings, badge templates, or step payloads are too large or awkward to store inline.
3. **Repo-backed versioned files are the default backing for seeded mock data and static or rarely changed configuration stores** unless runtime mutability becomes a real POC requirement.
4. **Local development should generally mirror the AWS logical store split using SQLite for operational stores** unless a component has a strong reason not to.
5. **LLM-generated artifacts should generally be persisted even when reuse is intentionally bypassed.** The preferred escape hatch for LLM testing is "skip lookup/reuse on read," not "do not store the generated artifact at all."
6. **Logical stores remain separate even when they share one physical technology.** In particular, idempotency records and execution logs should not collapse into one undifferentiated store.

## Store Mapping

| Logical store | Phase 1 posture | Target by end of POC | Initial backing | Likely target backing | Notes |
| --- | --- | --- | --- | --- | --- |
| **Mock LMS Resource / Event Data Store** | Active | Active | Repo-committed JSON fixtures | Repo-committed JSON fixtures unless runtime mutability becomes necessary | Read-only seeded demo data does not need a separate runtime database for the POC. |
| **Validated Workflow Actions Plan Store** | Not yet an active reusable store in the no-LLM slice | Active; validated plans can be reviewed and optionally reused | No dedicated store required in Phase 1; capture inside execution artifacts if needed | DynamoDB metadata/index plus S3 for larger plan bodies when needed | Persist generated plans once this capability exists, but allow reuse lookup to be bypassed when the team wants to keep exercising the planning LLM. |
| **Versioned Action Registry** | Minimal/static | Active | Repo-backed versioned configuration | Repo-backed versioned configuration | A good fit for code review, explicit versioning, and low change frequency. |
| **Policy Store** | Not in active runtime use while the Policy Rules Service is out of scope | May become active again before the end of the POC | Repo-backed versioned configuration | Repo-backed versioned configuration unless operator-managed rule editing becomes a real POC need | The logical store should remain defined even when the service is temporarily out of scope. |
| **Workflow Action Plan Execution Logs** | Active | Active | DynamoDB in AWS; SQLite locally | DynamoDB as the primary operational store, with S3 spillover for large payloads when needed | This is the primary correlated execution record that the Orchestrator read API and Admin UI should rely on. |
| **Idempotency Store** | Active | Active | DynamoDB in AWS; SQLite locally | DynamoDB in AWS; SQLite locally | Keep separate from execution logs. |
| **Mapping Template Storage** | Not yet an active reusable store in the no-LLM slice | Active; generated mappings can be reviewed and optionally reused | No dedicated store required in Phase 1; deterministic mappings may live in code or versioned config | DynamoDB metadata/index plus S3 for larger mapping bodies when needed | Persist generated mapping specifications once this capability exists, but allow reuse lookup to be bypassed when the team wants to keep exercising the mapping LLM. |
| **Badge Template Storage** | Not yet an active reusable store in the no-LLM slice | Active; generated badge templates can be reviewed and optionally reused | No dedicated store required in Phase 1 | DynamoDB metadata/index plus S3 for larger template bodies when needed | Persist generated badge templates once this capability exists, but allow reuse lookup to be bypassed when the team wants to keep exercising the generation path. |
| **Delivery Targets Store** | Active but static/deterministic | Active | Repo-backed versioned configuration | Repo-backed versioned configuration unless runtime editing becomes a real POC need | The logical store exists even if the initial target set is small and stable. |
| **Source Fetch Rules Store** | Active | Active | Repo-backed versioned configuration | Repo-backed versioned configuration | The Context Builder depends on this store from the start because source fetch selection is deterministic integration logic. |

## Operational Store Patterns

For the operational AWS-backed stores:

- the Event Consumer should use a **conditional write** against the idempotency store rather than a fragile read-then-write duplicate check,
- the Event Consumer should create the idempotency record and the initial workflow execution record in a **single DynamoDB transaction** when practical,
- the Orchestrator should treat the workflow execution log store as the primary persisted execution trail for workflow and step status,
- and large step payloads, generated artifacts, or audit blobs should move to **S3 with references stored in DynamoDB** when inline storage becomes awkward.

The same logical separation should be preserved locally with SQLite-backed operational tables unless a component has a strong reason to use a different inspectable local mechanism.

## Rationale

- **Different stores have different storage shapes.** Operational workflow state, seeded mock data, versioned configuration, and reusable generated artifacts should not all be forced into the same backing pattern.
- **DynamoDB fits the AWS/serverless direction for operational state.** It is a strong fit for key-based lookup, idempotency, and workflow execution records without adding relational database operations early in the POC.
- **S3 is the right escape hatch for larger generated artifacts.** It keeps operational tables small while preserving auditability and reuse.
- **Repo-backed files are appropriate for static configuration and seeded demo data.** They support code review, explicit versioning, and low operational overhead.
- **"Persist but optionally bypass reuse" is the right compromise for LLM testing.** It preserves traceability and future reuse without preventing the team from repeatedly exercising the LLM-driven paths.

## Alternatives Considered

- **Postgres or Aurora as the primary operational store.** This would provide richer relational querying, but it adds operational weight and is not necessary for the key-based workflow state, idempotency, and audit patterns that dominate the POC.
- **One shared operational store with no meaningful logical separation.** This would simplify early infrastructure naming, but it weakens the architectural boundaries between idempotency, execution logs, generated artifacts, and configuration-backed stores.
- **Do not persist LLM-generated plans, mappings, or badge templates during the POC.** This would make it easier to force repeated LLM execution, but it would give up useful auditability, inspection, and future reuse. The chosen compromise is to persist artifacts while allowing lookup or reuse to be bypassed.
- **A dedicated runtime database for Mock LMS seeded data.** This could support later mutation-heavy demo behavior, but it is unnecessary for the current seeded-fixture approach and would add avoidable setup and maintenance overhead.

## Consequences

- The repo can move forward with component-level requirements and design docs against a shared storage vocabulary that covers the full POC rather than only the first slice.
- Phase 1 docs can now state temporary scope cuts or lookup bypass behavior without redefining the long-term role of a logical store.
- The Admin UI read path has an explicit storage home in the workflow execution logs owned by the Orchestrator.
- The Mock LMS fixture approach remains valid without prematurely introducing a separate runtime database for seeded demo data.
- If later POC work requires operator-managed editing, richer querying, or more relational reporting for selected stores, a follow-up ADR can refine the backing technology for those specific stores.
