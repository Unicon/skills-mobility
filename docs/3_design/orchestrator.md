# Orchestrator Design

Status: Draft
Date: 2026-06-23
Related: [Requirements](../2_requirements/orchestrator.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [Context Builder Design](./context-builder.md) · [Delivery Router Service Design](./delivery-router-service.md) · [LearnCard Profile Resolver Design](./learncard-profile-resolver.md) · [Target POC Architecture](./architecture/target-poc-architecture.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0015](../decisions/0015-orchestrator-execution-model.md)

## 1. Overview

The Orchestrator is the POC's **constrained plan executor**. It is the component that receives a started workflow, gathers the context needed for planning, obtains a workflow plan, executes the approved steps, and records the correlated execution trail.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service / workers | `services/orchestrator/` | Python 3.12 + FastAPI locally; Lambda + SQS in AWS | Plan acquisition, step execution, execution-state persistence, audit trail |

The design constraint is to keep the **execution model reusable** even though **Phase 1** is narrower than the target POC. Phase 1 should therefore use the same basic artifacts the final POC expects:

- a persisted execution record,
- a workflow plan artifact,
- an approved action vocabulary,
- explicit step boundaries,
- and persisted execution log metadata plus step results or references to them.

What changes between Phase 1 and the target POC is not the Orchestrator's role. What changes is which step implementations are real and which are stubbed.

## 2. Phase Split

The Orchestrator needs an explicit split between the **Phase 1 slice** and the **target POC** so the Phase 1 implementation stays small without hard-coding a dead-end flow.

| Concern | Phase 1 | Target POC |
|---|---|---|
| Workflow Actions source | Deterministic pre-target Workflow Actions stub returns `continue` for the supported happy-path events; deterministic delivery-phase Workflow Actions stub returns a pre-authored plan per selected target set | Workflow Actions LLM Decision Service is invoked twice per continue-path execution: once for pre-target gating and once for delivery-phase planning |
| Delivery targets | Deterministic stub always selects LearnCard issuance and wallet delivery | Delivery Targets LLM Decision Service selects targets from the available target set |
| Profile resolution | Real LearnCard Profile Resolver step | Same |
| Field Mapping seam | Explicit step seam remains in the Phase 1 plan, satisfied by deterministic no-op stubs | Field Mapping LLM Decision Service generates target-aware mapping specifications |
| Field Synthesis seam | Explicit step seam remains in the Phase 1 plan where it is meaningful, satisfied by deterministic no-op stubs | Field Synthesis LLM Decision Service generates human-facing synthesized values where required |
| Transformation steps | Two pragmatic payload-prep passes, each expressed through the relevant Field Mapping / Field Synthesis / Translation Executor seams | Full ADR-0008 transformation pipeline with stored mappings, synthesized fields, and reusable artifacts |
| Policy validation | Not a required standalone runtime dependency for the happy path because no live probabilistic output is introduced | Deterministic Policy Rules validation before side effects |
| Execution visibility | Minimal inspectable workflow + step records | Full correlated execution model for Admin UI |

The important design choice is that **Phase 1 still uses the final step seams**:

- pre-target Workflow Actions seam,
- delivery-target selection seam,
- delivery-phase Workflow Actions seam,
- field-mapping seam,
- field-synthesis seam,
- translation-executor seam,
- profile-resolution seam,
- and delivery-routing seam.

That keeps the executor stable while letting the step implementations mature over time.

Per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md), the Orchestrator should make **two** Workflow Actions calls on the continue path:

1. a pre-target gate call that decides whether the workflow terminates early or proceeds, and
2. a delivery-phase planning call that runs after Delivery Targets and receives the selected targets as inputs.

## 3. Recommended Runtime Shape

The useful minimal shape is:

```text
Event Consumer
  -> Orchestrator start boundary
      -> execution record creation/update
      -> Context Builder
      -> Workflow Actions pre-target gate
      -> Delivery Targets
      -> Workflow Actions delivery-phase plan boundary
      -> plan persistence
      -> executor loop
          -> step client(s)
          -> step result persistence
      -> terminal workflow outcome
```

The runtime should stay split conceptually into:

- **start / planner path** — receives the workflow, gets the context bundle, obtains the pre-target gate decision, obtains delivery targets when appropriate, obtains the delivery-phase plan, persists the governing artifacts, and makes the first ready step executable
- **executor path** — advances one step at a time, persists the result, determines the next ready step, and repeats until terminal state

Locally, those two paths can run inside one FastAPI process for simplicity. In AWS, ADR-0015's queue-driven planner/executor split should be used.

## 4. Plan Contract

### Why use the plan early

Phase 1 is intentionally not the final orchestrator, but it should still use the intended Workflow Actions artifacts early so the team is not forced to replace a hard-coded flow later.

That means the Phase 1 stub planner path should return real gating and delivery-planning artifacts rather than simply calling the next function inline in the workflow-start handler.

### Pre-target gate artifact

The first Workflow Actions call returns a small structured decision artifact rather than the delivery-phase plan itself.

The useful minimal shape is:

```json
{
  "decision": "continue_to_delivery_targets",
  "confidence": 1.0,
  "rationale": "Deterministic Phase 1 happy-path gate decision."
}
```

This gate decision is execution-scoped. It should be recorded on the workflow execution for inspection, but it should not be stored in the reusable delivery-phase plan store and it should not be looked up for reuse.

### Minimal Phase 1 plan shape

The second Workflow Actions call returns the delivery-phase plan. For Phase 1, that plan only needs the subset of fields the executor must actually use:

```json
{
  "plan_schema_version": "v1",
  "plan_id": "phase1-skill-mastered.v1",
  "generated_at": "2026-06-23T00:00:00Z",
  "generator": {
    "service_version": "phase1-workflow-actions-stub.v1",
    "model_identifier": "stub",
    "prompt_template_version": "phase1-static-plan.v1"
  },
  "applicability": {
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "selected_targets": ["learncard_issuer", "learncard_wallet"]
  },
  "confidence": 1.0,
  "rationale": "Deterministic Phase 1 LearnCard workflow.",
  "steps": []
}
```

The exact binding language for step inputs and conditions remains open. Phase 1 should keep this simple by using structured source references rather than inventing a second DSL. This document uses `type` for the step-classification field per [ADR-0011](../decisions/0011-orchestration-runtime-technology.md). The Phase 1 example uses only `type: call`, but the target-POC schema should still leave room for other step types such as `wait`, `for_each`, or `terminate`.

A minimal step can therefore look like:

```json
{
  "step_id": 1,
  "type": "call",
  "action_id": "resolve_learncard_profile",
  "inputs": {
    "learner_id_type": {
      "source": "literal",
      "value": "email"
    },
    "learner_id_value": {
      "source": "workflow",
      "path": "learner_identifier_value"
    }
  },
  "produces": "resolved_profile"
}
```

For the POC, integer `step_id` values are acceptable and keep the execution records compact. Human-readable meaning should live primarily in `action_id` and in optional step metadata.

Runtime configuration values such as `delivery_config_ref` should be attached to the workflow execution context by the Orchestrator itself. They are part of execution configuration, not fields the raw source event is expected to carry. For Phase 1, `delivery_config_ref` is loaded from an environment variable.

The Orchestrator should also treat the full Context Builder output as **opaque JSON**, not as a fully modeled Pydantic domain object. The workflow start contract, plan schema subset, and step result envelopes should use typed envelope fields, but the full LMS context bundle should remain flexible so source JSON can evolve during the POC without forcing a full schema rewrite.

The same principle applies to step results. Step result envelopes should carry typed metadata such as status, step id, action id, timing, and artifact references, while allowing step-specific opaque JSON payloads where the result shape varies by action. When a step input binding uses `{ "source": "step", "step_id": N }`, the executor resolves it to the full raw action return value for that step — or to a reference pointer when the value has been stored out-of-line as an artifact.

The context bundle returned by the Context Builder does not need to be duplicated into every later step record. In local single-process execution it may remain in memory for the lifetime of the run. In the AWS-shaped planner/executor model, where work crosses Lambda and SQS boundaries, the Orchestrator should persist the bundle once or persist it out-of-line and retain only a durable reference in execution state.

## 5. Phase 1 Plan Shape

For both supported event types, the stub planner should return the same broad step sequence. The payload contents differ by event type; the executor structure does not.

Recommended delivery-phase plan sequence for Phase 1:

1. `resolve_learncard_profile`
2. `generate_issuer_payload_mapping`
3. `generate_issuer_payload_synthesis`
4. `execute_issuer_payload_translation`
5. `issue_learncard_badge`
6. `generate_wallet_payload_mapping`
7. `execute_wallet_payload_translation`
8. `deliver_to_learncard_wallet`

That sequence is deliberate:

- the **delivery-target seam** remains outside the delivery-phase plan because the second Workflow Actions call already knows the selected targets,
- it keeps the **profile-resolution seam** in place as a real upstream prerequisite for LearnCard-specific steps,
- it keeps the **Field Mapping** seam in place for both issuer and wallet payload preparation,
- it keeps the **Field Synthesis** seam in place where it is actually relevant to the payload being prepared,
- and it keeps the **Translation Executor** seam in place for both issuer input preparation and wallet input preparation.

This is intentionally **not yet the full target transformation loop structure from ADR-0008**. Phase 1 uses two pragmatic payload-preparation passes because one pass prepares the LearnCard Issuer input and the second prepares the LearnCard Wallet input after the badge exists. The executor should treat these as ordinary actions so the later move to the final mapping/synthesis/execution flow is a step-implementation change, not an executor rewrite.

In the example below, `step_id` identifies one specific step occurrence inside one plan, while `action_id` identifies the reusable operation being invoked. They should not be assumed to be the same value: the same `action_id` may appear in multiple steps with different inputs, targets, or conditions.

### Example Phase 1 plan

```json
{
  "plan_schema_version": "v1",
  "plan_id": "phase1-skill-mastered.v1",
  "generated_at": "2026-06-23T00:00:00Z",
  "generator": {
    "service_version": "phase1-workflow-actions-stub.v1",
    "model_identifier": "stub",
    "prompt_template_version": "phase1-static-plan.v1"
  },
  "applicability": {
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "selected_targets": ["learncard_issuer", "learncard_wallet"]
  },
  "confidence": 1.0,
  "rationale": "Deterministic Phase 1 LearnCard workflow.",
  "steps": [
    {
      "step_id": 1,
      "type": "call",
      "action_id": "resolve_learncard_profile",
      "inputs": {
        "delivery_config_ref": { "source": "workflow", "path": "delivery_config_ref" },
        "learner_id_type": { "source": "literal", "value": "email" },
        "learner_id_value": { "source": "workflow", "path": "learner_identifier_value" }
      },
      "produces": "resolved_profile"
    },
    {
      "step_id": 2,
      "type": "call",
      "action_id": "generate_payload_mapping",
      "inputs": {
        "context_bundle": { "source": "workflow", "path": "context_bundle" },
        "delivery_target": { "source": "literal", "value": "learncard_issuer" },
        "event_type": { "source": "workflow", "path": "event_type" }
      },
      "produces": "issuer_mapping"
    },
    {
      "step_id": 3,
      "type": "call",
      "action_id": "generate_field_synthesis",
      "inputs": {
        "context_bundle": { "source": "workflow", "path": "context_bundle" },
        "mapping": { "source": "step", "step_id": 2 }
      },
      "produces": "issuer_synthesis"
    },
    {
      "step_id": 4,
      "type": "call",
      "action_id": "execute_translation",
      "inputs": {
        "context_bundle": { "source": "workflow", "path": "context_bundle" },
        "delivery_target": { "source": "literal", "value": "learncard_issuer" },
        "mapping": { "source": "step", "step_id": 2 },
        "synthesis": { "source": "step", "step_id": 3 },
        "resolved_profile": { "source": "step", "step_id": 1 }
      },
      "produces": "issuer_payload"
    },
    {
      "step_id": 5,
      "type": "call",
      "action_id": "issue_learncard_badge",
      "inputs": {
        "payload": { "source": "step", "step_id": 4 }
      },
      "produces": "issued_badge"
    },
    {
      "step_id": 6,
      "type": "call",
      "action_id": "generate_payload_mapping",
      "inputs": {
        "issued_badge": { "source": "step", "step_id": 5 },
        "delivery_target": { "source": "literal", "value": "learncard_wallet" }
      },
      "produces": "wallet_mapping"
    },
    {
      "step_id": 7,
      "type": "call",
      "action_id": "execute_translation",
      "inputs": {
        "issued_badge": { "source": "step", "step_id": 5 },
        "delivery_target": { "source": "literal", "value": "learncard_wallet" },
        "mapping": { "source": "step", "step_id": 6 },
        "resolved_profile": { "source": "step", "step_id": 1 }
      },
      "produces": "wallet_payload"
    },
    {
      "step_id": 8,
      "type": "call",
      "action_id": "deliver_to_learncard_wallet",
      "inputs": {
        "payload": { "source": "step", "step_id": 7 }
      },
      "produces": "wallet_delivery_result"
    }
  ]
}
```

## 6. Action Implementations

The executor should stay ignorant of whether an action is a stub or a real service. That choice belongs in the action registry or step client layer.

| Action id | Phase 1 implementation | Later target-PoC implementation |
|---|---|---|
| `workflow_actions_pre_target_gate` | Deterministic stub returns `continue` for the supported Phase 1 happy-path events | First Workflow Actions LLM call decides terminate vs continue |
| `select_delivery_targets` | Deterministic stub returns LearnCard issuance + wallet delivery | Delivery Targets LLM Decision Service |
| `workflow_actions_delivery_phase_plan` | Deterministic stub returns the delivery-phase plan for the selected targets | Second Workflow Actions LLM call generates the delivery-phase plan |
| `resolve_learncard_profile` | Real LearnCard Profile Resolver | Same |
| `generate_payload_mapping` | No-op stub | Field Mapping LLM Decision Service for the relevant transformation phase |
| `generate_field_synthesis` | No-op stub where the payload phase actually requires synthesis | Field Synthesis LLM Decision Service for the relevant transformation phase |
| `execute_translation` | Deterministic minimum mapping from the current inputs to the required target payload | Transformation Executor using stored/generated mappings |
| `issue_learncard_badge` | Delivery Router action -> LearnCard Issuer Adapter | Same |
| `deliver_to_learncard_wallet` | Delivery Router action -> LearnCard Wallet Adapter | Same |

This is the main reuse mechanism: the executor and persisted step model remain stable while the action implementations evolve.

## 7. Logical Modules

The initial service can stay small. Useful internal modules are:

- `api/` — local start endpoint, reusable-plan lookup control endpoints, stored-plan deletion endpoints, and local inspection endpoints
- `schemas/` — workflow start contract, pre-target gate schema, delivery-phase plan schema subset, step result envelope schema, and execution state schema; not exhaustive typed models for the full Context Builder bundle or all step-specific result payloads
- `planner/` — context-builder call, pre-target gate invocation, delivery-phase plan invocation or lookup, and artifact persistence
- `executor/` — step selection, input binding, step dispatch, result persistence, terminal-state evaluation
- `actions/` — Phase 1 step-dispatch map and later action-registry-backed step client bindings
- `clients/` — HTTP or Lambda-invoke clients for Context Builder, LearnCard Profile Resolver, and Delivery Router
- `store/` — execution, step, and delivery-phase plan persistence
- `audit/` — structured execution and step log emission

The Phase 1 stub actions do not need their own deployable services. They can live inside `actions/` as deterministic implementations behind the same interface the later service clients will use.

## 8. Execution Flow

### Planner path

1. Receive workflow start from the Event Consumer.
2. Load or create the workflow execution record and mark it `planning`.
3. Invoke the Context Builder with the raw event envelope.
4. Persist the returned context bundle once when cross-worker execution requires it, or persist a durable artifact reference to it.
5. Invoke the first Workflow Actions boundary. In Phase 1 this is the deterministic pre-target stub.
6. Record the gate decision in workflow execution metadata.
7. If the gate decision is `terminate`, mark the workflow complete with the named outcome and stop.
8. Invoke the Delivery Targets boundary.
9. Derive the reusable-plan lookup key(s) for the delivery-phase plan from the event, selected targets, and any other planning context dimensions the team decides are materially relevant.
10. If delivery-phase plan lookup is enabled and a matching stored plan is found, load that plan. If lookup is disabled or no match is found, invoke the second Workflow Actions boundary. In Phase 1 this is the deterministic delivery-phase stub.
11. If a looked-up plan fails required schema, registry, or policy validation, do not use it for the current execution; invoke the second Workflow Actions boundary to generate a fresh delivery-phase plan instead.
12. Persist the delivery-phase plan artifact or a reference to it.
13. If policy validation is active for the plan source, run it now before any side-effecting steps become executable.
14. Mark the first step ready for execution.

Reusable delivery-phase plan lookup should be configurable so the team can bypass stored-plan reuse during Workflow Actions LLM testing while still persisting generated delivery-phase plans for later inspection or reuse. For local development, exposing an API to toggle stored-plan lookup is reasonable. Exposing an API to delete stored plans is also reasonable when the team wants to force regeneration.

### Executor path

1. Load the next ready step.
2. Resolve its inputs from workflow context plus prior step outputs.
3. Invoke the bound action implementation.
4. Persist step status, inputs, outputs, timing, and error details.
5. Determine the next ready step.
6. Repeat until terminal success or failure.

For Phase 1, the executor may run all steps synchronously after planning in local mode. The important constraint is that each step result is still persisted as if it were a queue-driven worker transition.

## 9. Execution State and Storage

The Orchestrator should persist **execution log metadata**, not repeated full snapshots of every large payload after every step. The storage model should keep the execution trail inspectable while avoiding unnecessary duplication of the context bundle and large intermediate artifacts.

### Minimum workflow states

- `created`
- `planning`
- `ready`
- `running`
- `completed`
- `failed`

### Minimum step states

- `pending`
- `running`
- `succeeded`
- `skipped`
- `failed`

### Minimum persisted artifacts

For Phase 1, the smallest useful local persistence model is:

- `workflow_execution`
  - `execution_id`
  - `event_id`
  - `correlation_id`
  - `event_type`
  - `status`
  - `gate_decision`
  - `plan_id`
  - `context_artifact_ref`
  - `created_at`
  - `updated_at`
- `workflow_step_execution`
  - `execution_id`
  - `step_id`
  - `status`
  - `attempt`
  - `input_artifact_ref`
  - `output_artifact_ref`
  - `error_json`
  - `started_at`
  - `finished_at`
- `workflow_plan`
  - `plan_id`
  - `applicability_key_json`
  - `plan_json`
  - `created_at`
  - `last_used_at`
  - `updated_at`

The intended identity rules are:

- `execution_id` is the shared identifier across execution-scoped artifacts for one workflow run, such as `workflow_execution` and `workflow_step_execution`;
- `plan_id` identifies a reusable delivery-phase plan artifact that may be referenced by many executions;
- `workflow_execution.plan_id` links one execution to the delivery-phase plan artifact it actually used.

The practical storage rule should be:

- store the context bundle once per execution, or store it out-of-line and keep one durable reference;
- keep step records small and focused on execution log metadata;
- store large step payloads out-of-line only when they are worth preserving for troubleshooting or audit;
- use reusable delivery-phase plan lookup keys based on the event, source, selected targets, and any other materially relevant planning dimensions the team decides to include;
- keep stored delivery-phase plans until someone explicitly deletes them;
- avoid writing a full before/after copy of the context bundle for every step transition.

### AWS-shaped target

The AWS-shaped target should mirror ADR-0014:

- DynamoDB-backed execution and step state
- a separate logical store for reusable validated delivery-phase plans when plan reuse becomes active
- S3 spillover only when step payloads become too large for comfortable inline storage

## 10. Local vs AWS Invocation Model

The **logical contracts stay the same** in both environments. What changes is the transport.

| Concern | Local development | AWS-shaped target |
|---|---|---|
| Event Consumer -> Orchestrator | HTTP `POST` to a local start endpoint | SQS message from Event Consumer Lambda to planner Lambda |
| Planner -> executor handoff | In-process call or loopback HTTP inside the same local service | SQS message from planner worker to executor worker carrying `execution_id`, ready-step metadata, and artifact references rather than large context payloads |
| Context Builder call | `POST /build-context` over `localhost` or direct Python module call | Synchronous Lambda invoke |
| Workflow Actions pre-target boundary | In-process stub module | Separate Lambda-backed service boundary; deterministic stub first, LLM-backed later |
| Delivery Targets boundary | In-process stub module | Separate Lambda-backed service boundary; deterministic stub first, LLM-backed later |
| Workflow Actions delivery-phase boundary | In-process stub module | Separate Lambda-backed service boundary; deterministic stub first, LLM-backed later |
| LearnCard Profile Resolver call | `localhost` HTTP | Synchronous Lambda invoke |
| Translation actions | In-process deterministic stubs | Separate Lambda-backed service boundary when externalized, or internal executor action while still stubbed |
| Delivery Router call | `localhost` HTTP | Synchronous Lambda invoke for the intended Lambda-per-service deployment |
| Execution store | SQLite | DynamoDB |

The Orchestrator should therefore hide transport behind step clients. The executor should know only that it is invoking `resolve_learncard_profile` or `issue_learncard_badge`, not whether that happens through HTTP or Lambda invoke.

This matters for payload size as well as abstraction. SQS messages are size-limited, so the worker-to-worker queue contract should stay small and pointer-oriented rather than carrying the full Context Builder result or large downstream payloads.

## 11. Testing

- Unit tests for plan loading, input binding, action-registry lookup, step-state transitions, and terminal-state evaluation
- Unit tests for the deterministic Phase 1 stubs, especially the issuer-payload and wallet-payload translation actions
- API tests for the local workflow start endpoint
- Integration tests with fake Context Builder, LearnCard Profile Resolver, and Delivery Router boundaries
- End-to-end local tests for `skill_mastered` and `course_completed`

Routine Orchestrator tests should not require live LearnCard access. That dependency belongs behind the downstream service boundaries.

## 12. Build Order

1. Define the workflow start contract, pre-target gate schema, delivery-phase plan schema subset, execution state schema, and step result envelope schema, while keeping the full Context Builder bundle and step-specific result payloads as opaque JSON rather than fully modeled Pydantic schemas.
2. Implement SQLite-backed workflow, step, and plan persistence.
3. Implement the planner path with Context Builder invocation, optional reusable delivery-phase plan lookup, a lookup-usage toggle for Workflow Actions testing, a stored-plan deletion mechanism, and deterministic stubs for the pre-target and delivery-phase Workflow Actions calls.
4. Implement the executor loop with a small static Phase 1 step-dispatch map rather than a full formal action registry.
5. Implement the deterministic Delivery Targets stub, the Field Mapping and Field Synthesis no-op stubs where applicable, and the deterministic Translation Executor stubs.
6. Wire the real LearnCard Profile Resolver and Delivery Router clients into the executor.
7. Add the local start endpoint and local inspection flow.
8. Introduce the fuller action registry and policy-validation hooks needed for the target POC.
9. Add the AWS worker adapters for planner/executor Lambda + SQS execution.
