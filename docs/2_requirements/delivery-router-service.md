# Delivery Router Service Requirements

Status: Draft
Date: 2026-06-22
Related: [Requirements overview](./README.md) · [Target POC Requirements](./target-poc-requirements.md) · [Phase 1 POC Slice](./phase-1-poc-slice.md) · [Design](../3_design/delivery-router-service.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md)

## 1. Purpose

The **Delivery Router Service** is the POC's stable internal delivery execution facade. It accepts already-approved delivery actions from the **Orchestrator**, dispatches them to the correct downstream adapter, applies shared delivery mechanics, and returns normalized results.

The router exists to keep delivery execution details out of the Orchestrator. It does **not** decide whether delivery should happen or how a target payload should be semantically shaped.

## 2. Scope

For the target POC, the Delivery Router Service is expected to support at least these downstream adapter actions:

- `issue_learncard_badge` via the **LearnCard Issuer Adapter**
- `deliver_to_learncard_wallet` via the **LearnCard Wallet Adapter**
- `deliver_to_smartresume` via a future **SmartResume Wallet Adapter**

For **Phase 1**, the required scope is narrower:

- `issue_learncard_badge` via the LearnCard Issuer Adapter
- `deliver_to_learncard_wallet` via the LearnCard Wallet Adapter

The router receives payloads that have already been validated upstream.

- In **Phase 1**, those payloads are prepared directly inside the **Orchestrator**.
- In the **full POC**, those payloads are expected to be substantially shaped by the **Field Mapping LLM Decision Service**, **Field Synthesis LLM Decision Service**, and **Transformation Executor**.

## 3. Logical Invocation Contract

The exact transport is a design concern. Regardless of transport, each router invocation SHALL carry a stable logical contract with at least:

| Field | Meaning |
|---|---|
| `action` | The delivery action to execute, such as `issue_learncard_badge` or `deliver_to_learncard_wallet` |
| `contract_version` | Version of the router-facing contract for that action |
| `adapter_key` or equivalent | Which adapter implementation should receive the action |
| `payload` | The already-shaped action-specific delivery payload |
| `workflow_id` | Workflow identifier from the Orchestrator |
| `execution_id` | Execution identifier for this run |
| `step_id` | Plan step identifier for correlated audit |
| `correlation_id` | End-to-end correlation id when available |
| `delivery_config_ref` or equivalent | Reference to delivery configuration or credentials to use |

## 4. Functional Requirements

- **FR-DR-1** The Delivery Router Service SHALL expose a stable internal invocation contract that is independent of any specific adapter runtime or SDK.
- **FR-DR-2** The Delivery Router Service SHALL validate the action name, contract version, and required envelope fields before dispatching an invocation.
- **FR-DR-3** The Delivery Router Service SHALL resolve the configured adapter binding for the requested action.
- **FR-DR-4** The Delivery Router Service SHALL invoke the appropriate downstream adapter and return a normalized result envelope to the Orchestrator.
- **FR-DR-5** The Delivery Router Service SHALL attach workflow, execution, step, and correlation identifiers to downstream adapter calls and delivery logs.
- **FR-DR-6** The Delivery Router Service SHALL apply shared timeout and retry behavior using deterministic configuration rather than adapter-specific business logic.
- **FR-DR-7** The Delivery Router Service SHALL record standardized delivery-attempt and delivery-result records suitable for audit and later Admin UI use.
- **FR-DR-8** The Delivery Router Service SHALL normalize adapter responses into a consistent success/failure shape regardless of the downstream adapter runtime.
- **FR-DR-9** The Delivery Router Service SHALL treat payloads as already semantically shaped for the target system and SHALL NOT perform substantive field mapping, schema translation, or synthesized-field generation.
- **FR-DR-10** The Delivery Router Service SHALL NOT choose delivery targets, decide workflow order, or suppress an approved delivery step for business reasons.
- **FR-DR-11** The Delivery Router Service SHALL support adding new adapters without requiring the Orchestrator to learn vendor-specific endpoint or SDK details.

## 5. Out of Scope

The Delivery Router Service does not own:

- delivery target selection,
- workflow planning or branching,
- source-data fetching,
- transformation mapping generation,
- synthesized field generation,
- deterministic policy validation, or
- the correlated workflow execution view owned by the Orchestrator.
