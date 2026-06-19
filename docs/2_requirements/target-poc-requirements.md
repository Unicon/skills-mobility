# Target POC Requirements

Status: Draft
Date: 2026-06-19
Related: [Stakeholder POC Requirements](./poc-requirements.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Target POC Architecture](../3_design/architecture/target-poc-architecture.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0012](../decisions/0012-mcp-client-layer-deferred.md)

## 1. Purpose

This document captures the **current working system-level requirements** for the POC after ADRs and follow-up design work refined the stakeholder starting point.

[`poc-requirements.md`](./poc-requirements.md) is preserved as the original stakeholder baseline. This document is the one that should evolve as the team clarifies scope, architecture, and implementation expectations.

## 2. Current Scope

The current target POC scope includes:

- Mock generation of learner and credential-related events
- Mock learner and skills data APIs
- A Mock LMS UI to allow for review of mock data and triggering events
- Event ingestion and workflow startup
- An orchestration runtime capable of processing incoming events
- Context aggregation for orchestration decisions
- Specialized LLM decision services for workflow planning, delivery target selection, field mapping, and field synthesis
- Deterministic transformation execution
- Deterministic policy validation
- Delivery to LearnCloud/LearnCard and SmartResume
- Audit logging of orchestration decisions, confidence scores, and delivery actions
- An Admin UI that exposes correlated workflow execution state

The current target POC scope does not include:

- Production-ready Open edX eventing infrastructure
- Production learner profile APIs
- A dedicated MCP Client Layer in the initial POC iteration
- Full policy/governance workflows
- Multi-tenant deployment concerns
- Human review workflows
- Complex branching or exception-heavy workflow behavior

## 3. Current Objectives

The current implementation planning objective is to validate that the POC can:

- Interpret learner and credential events
- Generate workflow, routing, and transformation decisions through specialized LLM services
- Keep deterministic control over policy validation, transformation execution, and delivery eligibility
- Deliver transformed learner credential data to downstream systems
- Maintain complete execution traceability for review and debugging

## 4. Current Component Set

The following components are the current working component model for the POC:

| Component | Core responsibility |
| --- | --- |
| **Mock LMS Demo UI** | Inspect seeded source data, trigger demo Actions, and display emitted events with correlation ids |
| **Mock LMS Event Producer** | Build and publish canonical mock events onto the event bus |
| **LMS Resource APIs** | Expose read-only Canvas-style source data for the demo UI and Context Builder |
| **Event Consumer** | Validate event envelopes, enforce ingress idempotency, and start workflow execution |
| **Orchestrator** | Execute validated workflow plans, manage step state, and expose a unified execution view |
| **Context Builder** | Deterministically fetch and assemble normalized decision context |
| **Workflow Actions LLM Decision Service** | Generate the abstract workflow plan |
| **Delivery Targets LLM Decision Service** | Select downstream delivery targets |
| **Field Mapping LLM Decision Service** | Generate structured mappings and synthesis placeholders |
| **Field Synthesis LLM Decision Service** | Generate human-facing synthesized field values |
| **Transformation Executor** | Deterministically execute mappings and produce target payloads |
| **Policy Rules Service** | Deterministically validate plans, routing decisions, payloads, and delivery eligibility |
| **Delivery Router / Target Adapters** | Deliver validated payloads to LearnCloud/LearnCard and SmartResume |
| **Admin UI** | Expose per-workflow execution progress, rationale, confidence scores, and delivery outcomes |

The detailed current ownership model lives in the [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md).

## 5. Cross-Cutting Requirements

- LLM output MUST NOT flow directly to downstream delivery without deterministic validation by the **Policy Rules Service**.
- The **Orchestrator** MUST own the correlated execution view consumed by the **Admin UI**.
- The **Context Builder** MUST keep source-data fetching deterministic and versionable.
- The system MUST maintain audit records for workflow execution, including event identifiers, workflow identifiers, decision outputs, confidence scores, delivery results, and error conditions.
- MCP is deferred from the initial POC component model unless a later ADR reintroduces it for a concrete use case.

## 6. Success Criteria

The current target POC will be considered successful if it demonstrates:

### Orchestration

- Reliable end-to-end workflow execution
- Successful event correlation and tracking
- Clear workflow visibility and traceability through correlated execution records

### LLM behavior

* Accurate transformation recommendations  
* Accurate routing decisions  
* Consistent structured outputs  
* Explainable orchestration reasoning  
* Acceptable confidence scoring behavior

### Delivery and controls

- Successful delivery to LearnCloud/LearnCard
- Successful delivery to SmartResume
- Successful deterministic validation and audit logging of all execution steps
