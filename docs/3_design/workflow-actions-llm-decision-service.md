# Workflow Actions LLM Decision Service Design

Status: Draft
Date: 2026-07-10
Related: [Requirements](../2_requirements/workflow-actions-llm-decision-service.md) · [Orchestrator Design](./orchestrator.md) · [Field Mapping LLM Decision Service Design](./field-mapping-llm-decision-service.md) · [Delivery Targets LLM Decision Service Design](./delivery-targets-llm-decision-service.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Bedrock tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Overview

The **Workflow Actions LLM Decision Service** is the top-level planner of the orchestration architecture. Per [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md), it generates the complete orchestration plan the runtime executes, and per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) it does so through a **two-stage hierarchical model**:

`Should this event proceed at all — and if so, what ordered steps get from this event to the selected targets?`

Those are two separate questions, answered by two separate invocations at two fixed orchestration boundaries (ADR-0009 "Resulting Invocation Order"):

| Stage | Boundary | Question | Output |
| --- | --- | --- | --- |
| Pre-target gate | Before Delivery Targets | Terminate early, or continue? | Execution-scoped gate decision |
| Delivery-phase plan | After Delivery Targets | What ordered plan reaches the selected targets? | Reusable delivery-phase plan artifact |

ADR-0007 left open whether Workflow Actions should be a peer of the other services or their hierarchical parent. ADR-0009 resolves this in favor of the **hierarchical model**, with the refinement that the hierarchy is split across a gate call and a plan call rather than a single up-front plan. The service is therefore the planner; the Orchestrator ([ADR-0011](../decisions/0011-orchestration-runtime-technology.md)) is the faithful, constrained executor of what it produces.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/workflow-actions/` | Python 3.12 + FastAPI locally; Lambda in AWS | Pre-target gate decision + delivery-phase plan generation |

This service replaces the two deterministic Orchestrator planner stubs — `workflow_actions_pre_target_gate` and `workflow_actions_delivery_phase_plan` ([Orchestrator Design](./orchestrator.md) §6) — behind the same two planner seams, without changing the executor or the gate/plan contracts.

## 2. What the Service Produces

The service produces two artifacts, one per stage.

1. a **pre-target gate decision** — small, execution-scoped, recorded on the workflow execution and never reused (ADR-0009 "Artifact reuse")
2. a **delivery-phase plan artifact** — the ordered, executor-neutral plan the runtime validates and executes, eligible for reuse

### Pre-target gate decision

The gate response mirrors the shape the Orchestrator already records ([Orchestrator Design](./orchestrator.md) §4):

```json
{
  "decision": "continue_to_delivery_targets",
  "confidence": 0.98,
  "rationale": "skill_mastered at a parent-competency level; no disqualifier present."
}
```

`decision` is either `continue_to_delivery_targets` or a named early-termination outcome (for example `terminate_sub_competency`, `terminate_failing_grade`, `terminate_badge_not_accepted`). The exact set of named terminate outcomes is an open question (see §12); the field is a discriminated string so new outcomes can be added without a contract change. This decision is execution-scoped: it is recorded in workflow execution metadata but not stored in the reusable-plan store and not looked up for reuse ([FR-OR-20](../2_requirements/orchestrator.md); ADR-0009).

### Delivery-phase plan artifact

The stored plan is the delivery-phase plan defined in [Orchestrator Design](./orchestrator.md) §5 and [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §4. This service is the LLM-backed producer of exactly that artifact — the same shape the Phase 1 stub produces deterministically. Recommended shape:

```json
{
  "plan_schema_version": "v1",
  "plan_id": "skill_mastered.learncard.v1",
  "generated_at": "2026-07-10T00:00:00Z",
  "generator": {
    "service_version": "workflow-actions.v1",
    "model_identifier": "<bedrock-model-id>",
    "prompt_template_version": "delivery_phase_plan.v1"
  },
  "applicability": {
    "event_type": "skill_mastered",
    "source_system": "mock_lms",
    "selected_targets": ["learncard_issuer", "learncard_wallet"]
  },
  "confidence": 0.94,
  "rationale": "Dual-target LearnCard issuance and wallet delivery.",
  "steps": [ { "step_id": 1, "type": "call", "action_id": "resolve_learncard_profile", "inputs": { "...": "..." }, "produces": "resolved_profile" } ]
}
```

The full 8-step plan body is the sequence in [Orchestrator Design](./orchestrator.md) §5 (`resolve_learncard_profile` → `generate_payload_mapping` → `generate_field_synthesis` → `execute_translation` → `issue_learncard_badge` → `generate_payload_mapping` → `execute_translation` → `deliver_to_learncard_wallet`). That sequence is the service's output contract: the named steps are how the plan references the Delivery Targets-selected work, the Field Mapping / Field Synthesis / Translation Executor seams, and the delivery actions (ADR-0007 hierarchical model). Delivery-target selection is deliberately **not** a step in this plan — it is already resolved before Stage 2 runs ([Orchestrator Design](./orchestrator.md) §5).

The immediate service response to the Orchestrator normally contains a reference to the stored plan, not the full plan inline (§4).

## 3. Runtime Shape

The two stages are separate entry points invoked at separate orchestration boundaries. The Orchestrator sequences them (ADR-0009 "Resulting Invocation Order"; [Orchestrator Design](./orchestrator.md) §3):

```text
Orchestrator planner path
  -> Context Builder (assembles context bundle)
  -> Workflow Actions: pre-target gate
       -> screen event/context free text for prompt injection
       -> build gate prompt + structured-output schema
       -> call Bedrock
       -> parse + validate gate decision
       -> return decision ref
  -> if terminate: end workflow with named outcome
  -> if continue: Delivery Targets (selects targets)
  -> Workflow Actions: delivery-phase plan
       -> screen event/context free text for prompt injection
       -> assemble prompt from context + selected_targets + action-registry view
       -> build plan structured-output schema
       -> call Bedrock
       -> parse structured plan
       -> validate: schema, registry conformance, binding resolvability, required steps
       -> store plan artifact
       -> return plan ref
  -> (deterministic Policy Rules validation, when active)
  -> executor runs the plan
```

Each stage uses **one Bedrock Converse request per invocation**. The gate call is intentionally narrow — a small classification-style decision — and the plan call is the larger structured-generation task. Splitting the plan generation into multiple Bedrock calls (for example, step selection then step rendering) is a later experiment to run only if plan quality is poor; the default is one call per stage (mirroring the Field Mapping design's one-call default).

The service does not fetch source context and does not execute anything. It reads the context bundle as opaque JSON supplied by the Orchestrator and reads its own configuration (prompt templates, model settings). The action-registry view it receives is a prompt-time projection owned by the Orchestrator/runtime (ADR-0011 §3), not something this service defines.

## 4. Response Contract

Both stages return small synchronous responses; the substantive artifact is stored and referenced.

Pre-target gate response:

```json
{
  "status": "succeeded",
  "decision": "continue_to_delivery_targets",
  "confidence": 0.98,
  "rationale": "...",
  "llm_invocation_log_ref": "llmcall:g-123"
}
```

Delivery-phase plan response:

```json
{
  "status": "succeeded",
  "plan_ref": "plan:skill_mastered.learncard.v1",
  "confidence": 0.94,
  "rationale": "...",
  "llm_invocation_log_ref": "llmcall:p-456"
}
```

The gate decision is small enough to return inline; the Orchestrator records it on the execution ([FR-OR-20](../2_requirements/orchestrator.md)). The plan is returned by reference — the Orchestrator persists the plan artifact (or a reference to it) and passes `plan_id` through to the executor ([Orchestrator Design](./orchestrator.md) §4/§9). For local debugging only, an inline-expansion mode MAY return the full plan; that is not the default production-like path. The Orchestrator does not need all model metadata inline if it can retrieve that detail through the logged reference.

## 5. Request Contract

### Pre-target gate request

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "event_type": "skill_mastered",
  "event": { "...": "raw event envelope" },
  "context_bundle": { "...": "opaque context JSON" },
  "policy_context": { "...": "optional deterministic policy signals" }
}
```

The gate stage reasons over the event and context alone, because it must be able to disqualify before Delivery Targets runs (ADR-0009 Context; [FR-WA-3](../2_requirements/workflow-actions-llm-decision-service.md)).

### Delivery-phase planning request

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "event_type": "skill_mastered",
  "source_system": "mock_lms",
  "event": { "...": "raw event envelope" },
  "context_bundle": { "...": "opaque context JSON" },
  "selected_targets": ["learncard_issuer", "learncard_wallet"],
  "action_registry_view": [
    {
      "action_id": "resolve_learncard_profile",
      "description": "Resolve a LearnCard profile and DID for a learner identity.",
      "input_schema": { "...": "..." },
      "output_schema": { "...": "..." },
      "side_effecting": false
    }
  ]
}
```

`selected_targets` is supplied because Stage 2 reasons over the actual chosen targets, which is the whole point of the two-stage model (ADR-0009 "It gives the second planning call the target information it actually needs"). `action_registry_view` is the prompt-time projection of the versioned action registry (ADR-0011 §3): the plan may reference only these `action_id` values, and the same registry version validates the plan.

The context bundle is treated as opaque JSON on both stages ([Orchestrator Design](./orchestrator.md) §4). Prompt templates, model IDs, temperatures, and other runtime settings are service configuration, not per-request business inputs.

## 6. LLM Invocation and Prompting Strategy

Each stage makes **one Bedrock Converse request**, each with its own system prompt, request message, and structured-output schema.

### Pre-target gate prompt

The system prompt should tell the model:

- it is deciding only whether the workflow proceeds to delivery-target selection or terminates with a named business outcome — it is not planning steps,
- the disqualifiers it must recognize from event/context alone: sub-competency outcomes not warranting a credential, failing grades, and unaccepted badges (ADR-0009 Context),
- that a `continue_to_delivery_targets` decision is the default when no disqualifier is present,
- and that it must emit `decision`, `confidence`, and `rationale`.

The gate output schema constrains `decision` to the known enumerated set plus a mechanism for the model to name the terminate reason.

### Delivery-phase plan prompt

The system prompt should tell the model:

- it is generating an ordered, executor-neutral plan that gets from the event and context to the already-selected delivery targets,
- it may reference only the `action_id` and step `type` values in the supplied action-registry view (ADR-0011 §3/§4),
- how to express step input bindings using the declarative `literal` / `workflow` / `step` source-reference form ([Orchestrator Design](./orchestrator.md) §4), and that it must not emit code, URLs, or credentials,
- that delivery-target selection is not a step (targets are already selected),
- that profile resolution is a prerequisite for LearnCard-specific steps, and the Field Mapping / Field Synthesis / Translation Executor seams appear where the payload phase requires them (§5; [FR-OR-14/15](../2_requirements/orchestrator.md)),
- and that it must emit plan-level `confidence` and `rationale`, and MAY emit per-step rationale.

The plan output schema constrains the response to the plan artifact shape in §2 (`applicability`, ordered `steps[]` with `step_id`/`type`/`action_id`/`inputs`/`produces`, `confidence`, `rationale`).

### Prompt tuning emphasis

Prompt tuning for this service will likely focus on two boundaries that are the key POC evaluation questions for it:

- the gate's `terminate`-vs-`continue` boundary, especially the structural interpretation of flat Canvas outcomes as sub-competencies (ADR-0009 Context),
- and the plan's step-selection correctness: which steps are required, their order, and correct input bindings.

Prompt templates live in version-controlled files so changes are reviewable and comparable against the frozen evaluation corpus (ADR-0013). Bedrock models do not browse the web; any external grounding must be supplied explicitly and is out of scope for the first round of POC testing.

## 7. Bedrock Invocation Design

### Primary platform

Amazon Bedrock is the POC's primary managed inference platform per [ADR-0010](../decisions/0010-llm-model-access-strategy.md). The service interacts with model providers through a **thin provider adapter** rather than embedding Bedrock-specific request construction in service logic, so the provider can be swapped per stage later. The adapter targets Bedrock's **Converse API** — a system prompt plus role-labeled messages returning a standardized response. In this server-to-server pipeline the Bedrock `user` role message is an application-built request message, not a human chat message.

Per-stage interaction sequence:

1. screen free-text values from the event and context bundle for prompt-injection attempts ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)) before they reach the prompt
2. build the stage's prompt and structured-output schema
3. call the provider adapter, which invokes Bedrock `Converse` through the AWS SDK
4. parse the returned structured object
5. validate it (gate decision, or plan against registry/bindings/required steps)
6. store the artifact (plan) or record the decision

Bedrock structured outputs can enforce JSON-schema-conformant results for Converse requests; first-time schema compilation can add latency before the compiled grammar is reused, which should be expected during development. Sources: [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) and [Boto3 `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).

### Recommended starting settings

- `temperature`: `0.0` for both stages (structured decision and structured plan)
- `max_tokens`: high enough to return the full plan for the largest expected `selected_targets` set
- one baseline Bedrock model across services initially, then per-stage tuning later — the gate is a lighter reasoning task than plan generation and may warrant a different model once the baseline is proven (ADR-0010 reasoning-profile note: Workflow Actions is open-ended conditional planning)

### Access pattern

- local live mode: use the normal AWS SDK credential chain
- AWS deployment: use IAM roles for Lambda or the hosting runtime

No separate API-key layer is introduced for a Bedrock-backed service.

## 8. Validation

The service validates before reporting success. Structural validity alone is not success ([FR-WA-12/21/27](../2_requirements/workflow-actions-llm-decision-service.md)).

Pre-target gate validation:

1. parse the structured model response
2. verify `decision` is one of the allowed values and `confidence`/`rationale` are present

Delivery-phase plan validation (hard Layer-A gates, ADR-0013):

1. parse the structured model response
2. verify plan-schema validity and that `confidence`/`rationale` are present
3. verify every step's `action_id` and `type` exist in the supplied action-registry view (registry conformance, ADR-0011 §3)
4. verify every step input binding is resolvable: `workflow` paths exist in the workflow context contract, and every `{ "source": "step", "step_id": N }` reference points to a step that runs and `produces` a value before this step (dependency resolution)
5. verify the required steps for the applicability are present — for the LearnCard dual-target path, at least profile resolution, issuer-payload mapping/synthesis/translation, issuance, wallet-payload mapping/translation, and wallet delivery ([FR-WA-22](../2_requirements/workflow-actions-llm-decision-service.md); [Orchestrator Design](./orchestrator.md) §5)
6. store only validated plans as successful results

The service must not silently fall back to a hand-authored deterministic plan when model output is bad — that would defeat the POC's purpose. Invalid outputs are stored as **failed plan artifacts** or failed invocation records with their validation errors attached: not reusable as successful plans, but valuable evidence for prompt tuning and model comparison.

This service's validation is distinct from the deterministic **Policy Rules** validation ([ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §2), which the Orchestrator runs between plan generation and execution when active. The two together form the safety layer that does not depend on LLM reasoning ([FR-OR-23](../2_requirements/orchestrator.md); ADR-0007): the service will never let an unvalidated plan reach the executor, and the runtime never executes a plan that has not passed policy validation when active. No Policy Rules service design exists yet in this repo, so today the exact policy rule set is stated intent, not a verified contract.

### Capability Evaluation (Layer B)

The checks above are hard gates (ADR-0013 Layer A), not a capability verdict. The service's Layer B capability evaluation is a **deterministic comparator** in the shared DeepEval harness ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)), run against the frozen corpus:

- the gate decision matched against the scenario's canonical terminal outcome,
- and the plan matched against the scenario's canonical expected plan, including expected required or forbidden major steps (ADR-0013 Layer B, Workflow Actions row).

This is plain code, not an LLM-as-judge metric; no judge-model cost applies.

## 9. Repair Retry Mode

A **repair retry** feeds a validation error back to the model for another attempt. It can be useful for experimentation but must not be hidden in the authoritative evaluation path, or the POC stops measuring "can the model plan in one real attempt?" and starts measuring "can we rescue a bad attempt with scaffolding?"

Recommended rule:

- authoritative evaluation mode: exactly one model attempt per stage
- optional developer repair mode: explicit, off by default, separately logged (whether a retry was used, how many, the triggering validation error, and whether the final artifact required repair)

The POC does not need to define an acceptable retry rate yet; the first step is to measure it explicitly if the feature is on.

## 10. Stored Plan Reuse

Only delivery-phase plans are eligible for reuse; the pre-target gate decision is never stored for reuse (ADR-0009 "Artifact reuse"; ADR-0011 §8). Reuse is keyed by applicability (at minimum event type, source system, and selected targets) with exact-match lookup in v1 ([FR-OR-28/29](../2_requirements/orchestrator.md)).

Reuse lookup is owned by the **Orchestrator**, not this service ([Orchestrator Design](./orchestrator.md) §8): the Orchestrator decides whether to look up a stored plan or invoke this service to regenerate, and re-validates a looked-up plan before use. This service is the generator invoked when lookup is disabled, misses, or a stored plan fails validation.

Consistent with [ADR-0014](../decisions/0014-poc-storage-strategy.md), the default POC evaluation path is **fresh generation with reuse bypassed on read**, while generated plans are still persisted for inspection and later reuse:

- default local/test setting: reuse lookup disabled (generate fresh), plans still stored
- production-like setting: reuse lookup enabled

## 11. Observability and Evaluation Data

The service stores enough per-invocation data to evaluate output quality, cost, and tuning over time, for both stages. At minimum, each invocation record or artifact linkage should recover:

- `execution_id`
- stage (`pre_target_gate` or `delivery_phase_plan`)
- `event_type`
- `source_system`
- `selected_targets` (delivery-phase stage)
- prompt-template version
- model ID
- provider
- generation settings such as temperature
- input token count when available
- output token count when available
- latency
- the raw structured model output or a stable reference to where it is stored
- model-reported `confidence`
- model-reported `rationale`
- gate `decision` (gate stage) or `plan_id` (plan stage)
- validation outcome (including which hard gate failed, if any)
- whether repair retry mode was enabled and whether it was used
- `corpus_scenario_id`, present only for invocations run against the frozen ADR-0013 evaluation corpus (absent for live production invocations), formatted as `{event_type}.{scenario_slug}.v{version}` per [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) §8

This data supports comparing prompt versions, model choices, gate accuracy, plan-step correctness, retry behavior, and cost/latency tradeoffs. Per [ADR-0010](../decisions/0010-llm-model-access-strategy.md), this metadata flows into the Orchestrator's audit trace alongside other step data rather than a parallel observability stack.

## 12. Suggested Module Layout

The implementation can stay small:

```text
workflow_actions/
  contracts.py
  prompt_templates/
    pre_target_gate.v1.md
    delivery_phase_plan.v1.md
  action_registry_view.py
  prompt_builder.py
  llm_adapter.py
  bedrock_adapter.py
  replay_adapter.py
  validators.py
  plan_store.py
  service.py
  api.py
```

Responsibilities:

- `contracts.py`: gate and plan request/response schemas plus the stored plan artifact schema
- `prompt_templates/`: version-controlled system prompts, one per stage
- `action_registry_view.py`: parse and hold the prompt-time action-registry projection supplied by the Orchestrator/runtime (ADR-0011 §3); the registry itself is owned by the runtime, not this service
- `prompt_builder.py`: render each stage's system prompt and request message from the loaded inputs
- `llm_adapter.py`: define the provider-adapter protocol and shared result shape
- `bedrock_adapter.py`: implement the provider adapter using Bedrock `Converse` plus invocation-log capture
- `replay_adapter.py`: deterministic local replay without live Bedrock access
- `validators.py`: gate-decision validation and plan validation (schema, registry conformance, binding resolvability, required-step presence)
- `plan_store.py`: persist delivery-phase plan artifacts (and failed artifacts)
- `service.py`: orchestration of screen → prompt → model → validation → store → response, per stage
- `api.py`: FastAPI and Lambda entrypoint boundary exposing both stages

## 13. Build Order

Recommended implementation order:

1. Define the two request contracts (gate, plan) and the ref-returning response contracts.
2. Define the stored delivery-phase plan artifact schema (aligned to [Orchestrator Design](./orchestrator.md) §5 / ADR-0011 §4) and the gate decision schema.
3. Implement gate-decision validation and plan validation (schema, registry conformance, binding resolvability, required-step presence).
4. Add a deterministic replay adapter and fixture-driven tests for both stages.
5. Add the provider-adapter boundary, the Bedrock implementation, and the two prompt templates.
6. Wire the Orchestrator's two planner seams (`workflow_actions_pre_target_gate`, `workflow_actions_delivery_phase_plan`) to this service, replacing the deterministic stubs behind the same contracts.
7. Enable live Bedrock mode for prompt and model iteration, keeping reuse lookup disabled by default for honest evaluation.

That order keeps the service measurable and honest from the start, and lets it drop in behind the existing Orchestrator seams without an executor change.

## 14. Implementation Decisions

Decisions made during pre-development design review that are not already captured in ADRs.

### Two entry points, one service

The two stages live in one deployable service with two entry points rather than two separate services. They share the provider adapter, validation library, and logging, but use distinct prompt templates, output schemas, and (optionally) model configuration. This matches ADR-0009's "two Workflow Actions contracts" without doubling the deployable surface.

### Starting model

The service begins on the **same baseline Bedrock model as the other LLM Decision Services** (ADR-0010: all services start on one model to establish an end-to-end pipeline, with per-service differentiation later). Because Workflow Actions is the most open-ended reasoning task of the four (ADR-0010 reasoning profiles), it is a likely early candidate for a more capable model once the baseline is proven. The exact invocable Bedrock model ID should be verified against the current AWS Bedrock model catalog at implementation time and kept as runtime configuration, not hardcoded. Temperature is `0.0` for both stages per §7.

### Plan artifact storage for local development

**File-based JSON storage** is the local development approach for delivery-phase plan artifacts, keyed by the applicability signature (`event_type` + `source_system` + `selected_targets`). This avoids a running-infrastructure dependency during local development while preserving the same logical `plan_store.py` interface that a cloud store backs in AWS ([ADR-0014](../decisions/0014-poc-storage-strategy.md): DynamoDB for plan metadata, S3 spillover for large plans). Reuse-key ownership and lookup remain with the Orchestrator ([Orchestrator Design](./orchestrator.md) §9); this service only writes plan artifacts and reads its own configuration.
