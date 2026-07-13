# Workflow Actions LLM Decision Service Requirements

Status: Draft
Date: 2026-07-10
Related: [Requirements overview](./README.md) · [Target POC Requirements](./target-poc-requirements.md) · [Orchestrator Requirements](./orchestrator.md) · [Design](../3_design/workflow-actions-llm-decision-service.md) · [Orchestrator Design](../3_design/orchestrator.md) · [Field Mapping LLM Decision Service Requirements](./field-mapping-llm-decision-service.md) · [Delivery Targets LLM Decision Service Requirements](./delivery-targets-llm-decision-service.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Purpose

The **Workflow Actions LLM Decision Service** is the top-level planner of the orchestration architecture. Per [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md), it "generates the complete orchestration plan specifying all steps the workflow should execute for this event," and the orchestration engine's role is to execute that plan faithfully. Per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md), it does this through a **two-stage hierarchical model** rather than one call:

- **Stage 1 — pre-target gate:** decide whether the workflow terminates early with a named business outcome or continues to Delivery Targets (ADR-0009 "Stage 1: Pre-target gate").
- **Stage 2 — delivery-phase planning:** after Delivery Targets has run, produce the ordered delivery-phase plan that gets from the event and context to the selected target systems (ADR-0009 "Stage 2: Delivery-phase planning").

The plan this service produces references the Delivery Targets and Field Mapping/Field Synthesis/Translation Executor services as **named steps**, not as embedded logic (ADR-0007 hierarchical model; [Orchestrator Design](../3_design/orchestrator.md) §5).

The primary POC question for this service is whether an LLM can make the gate decision and generate an executable, policy-valid delivery-phase plan reliably enough to justify the architecture. The service must therefore keep both decisions visible and auditable, and it must never let its output reach execution without deterministic validation (ADR-0007 "subject to validation by the deterministic Policy Rules Service"; [Target POC Requirements](./target-poc-requirements.md) deterministic policy validation).

## 2. Responsibilities

The Workflow Actions LLM Decision Service is responsible for:

- accepting a **pre-target gate** request and returning a structured `terminate`/`continue` decision with confidence and rationale,
- accepting a **delivery-phase planning** request that includes the selected delivery targets and returning the delivery-phase plan inline (with optional storage reference),
- reading its own action registry directly to obtain the prompt-time action vocabulary and engineer-authored action descriptions (FR-WA-9a, FR-WA-9b),
- applying administrator-authored gating policy prose from its own action registry / pipeline config when making the gate decision (FR-WA-3a),
- generating steps that reference only actions in its own action registry (ADR-0011 §3),
- expressing per-step inputs as declarative bindings and per-step applicability/conditions,
- and attaching per-step and per-plan rationale and confidence for audit.

The service is not responsible for:

- executing the plan (that is the Orchestrator's constrained plan executor, ADR-0011),
- selecting delivery targets (that is the Delivery Targets LLM Decision Service),
- generating mapping JSONata or synthesized field text (those are the Field Mapping and Field Synthesis services),
- fetching source context (that is the deterministic Context Builder),
- performing the deterministic policy validation that gates its own output,
- or persisting execution state.

## 3. The Two Stages

Per [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) "Resulting Invocation Order," this service is invoked at two fixed points on the continue path.

| Stage | When it runs | Input focus | Output artifact |
| --- | --- | --- | --- |
| Pre-target gate | Before Delivery Targets, on every execution | Event context, learner context, policy context, workflow state | Execution-scoped gate decision (`terminate` or `continue`) with confidence and rationale |
| Delivery-phase plan | After Delivery Targets, on the continue path only | Everything above plus the selected delivery targets and the available action vocabulary | Ordered delivery-phase plan artifact |

The two stages are distinct requests with distinct contracts (ADR-0009 "Two Workflow Actions contracts"). Only the delivery-phase plan is eligible for reuse; the pre-target gate decision is execution-scoped and re-run per event (ADR-0009 "Artifact reuse").

The gate must be able to terminate for cases visible from event or context alone, including sub-competency `skill_mastered` events that should not issue a credential, failing `course_completed` events, and badge-awarded events where the badge has not yet been accepted (ADR-0009 Context and "It preserves early termination").

## 4. Inputs and Outputs

### Pre-target gate request inputs

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Tie the request to one workflow execution and its logs |
| `event_type` and raw event envelope | Identifies the triggering event to be gated |
| Context bundle | The assembled learner/learning context from the Context Builder, treated as opaque JSON ([Orchestrator Design](../3_design/orchestrator.md) §4) |
| Policy context | Any deterministic policy signals relevant to early termination (ADR-0007 Workflow Actions inputs) |

Context bundle and policy context are accepted by the gate for completeness and possible future use, but the gate's primary reasoning is over the event and context alone. Their inclusion does not change the gate's scope (see §3).

The service reads its gating policy prose directly from its own action registry / pipeline config — the Orchestrator does **not** pass the registry in as an input (see FR-WA-9a).

### Delivery-phase planning request inputs

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Tie the request to one workflow execution and its logs |
| `event_type`, `source_system`, and event envelope | Anchor the plan's applicability and step literals |
| Context bundle | Same opaque context bundle used at the gate stage |
| `selected_targets` | The delivery targets chosen by the Delivery Targets service; the plan is generated with these known (ADR-0009 Stage 2) |

The Orchestrator does **not** fetch the action registry and pass it in as an input. The service has direct access to its own action registry (see FR-WA-9a). The service similarly resolves its own prompt-time action-registry view internally (ADR-0011 §3).

Prompt templates, model IDs, temperatures, and other LLM runtime settings are configuration of the service runtime, not primary business inputs.

### Pre-target gate output

The gate response mirrors the small decision artifact the Orchestrator already records ([Orchestrator Design](../3_design/orchestrator.md) §4, "Pre-target gate artifact"):

| Output | Purpose |
| --- | --- |
| `decision` | `continue_to_delivery_targets` or a named `terminate` outcome |
| `confidence` | Model-reported confidence in the gate decision |
| `rationale` | Human-readable explanation for audit |
| `llm_invocation_log_ref` | Correlates to detailed invocation metadata in execution logs |

### Delivery-phase plan output

The plan is small enough that the service returns it directly in the synchronous response. A `plan_ref` (`plan_id`) MAY be included for storage correlation, but the Orchestrator does not need to make a second round-trip to retrieve the plan body.

| Output | Purpose |
| --- | --- |
| `plan` | The full delivery-phase plan artifact, returned inline |
| `plan_ref` (`plan_id`) | Optional reference to the stored plan artifact for storage correlation |
| `confidence` | Model-reported confidence in the plan |
| `rationale` | Plan-level rationale for audit |
| `llm_invocation_log_ref` | Correlates to detailed invocation metadata |
| Terminal status / failure details | Tells the Orchestrator whether planning succeeded |

The plan artifact carries the full `plan_schema_version`, `generator`, `applicability`, ordered `steps[]`, and rationale shape defined in [Orchestrator Design](../3_design/orchestrator.md) §5 and [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §4.

## 5. Functional Requirements

- **FR-WA-1** The service SHALL expose two distinct decision contracts: a pre-target gate contract and a delivery-phase plan contract, consistent with the two-stage hierarchical model of [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md).
- **FR-WA-2** The pre-target gate invocation SHALL run before Delivery Targets and SHALL return exactly one decision: `continue_to_delivery_targets`, or a named early-termination outcome.
- **FR-WA-3** The pre-target gate SHALL be able to terminate the workflow for disqualifiers visible from the event or context alone, including at least: sub-competency `skill_mastered` events not warranting a credential, failing-grade `course_completed` events, and badge-awarded events where the badge is not yet retrievable because acceptance has not occurred (ADR-0009 Context). The gate SHALL reason over administrator-authored **gating policy prose** stored in the action registry / pipeline config (see FR-WA-3a).
- **FR-WA-3a** The action registry / pipeline config SHALL store administrator-authored prose describing when the pre-target gate should terminate early. The gate prompt SHALL include this prose as context so the LLM can apply it. This gating prose is analogous to the admin-authored target descriptions used by the Delivery Targets service. It is stored in the action registry / pipeline config and is NOT delegated to a separate Policy Rules service (which is out of POC scope).
- **FR-WA-4** The pre-target gate decision SHALL be execution-scoped and SHALL NOT be treated as a reusable artifact (ADR-0009 "Artifact reuse"). The corresponding Orchestrator-side constraint — that it SHALL NOT perform reusable-plan lookup for the gate decision — is stated in [FR-OR-20](./orchestrator.md) and is an Orchestrator requirement, not a requirement on this service.
- **FR-WA-5** The delivery-phase planning invocation SHALL run only on the continue path, after Delivery Targets, and SHALL receive the selected delivery targets as an input (ADR-0009 Stage 2).
- **FR-WA-6** The delivery-phase planning invocation SHALL produce an ordered, executor-neutral plan artifact matching the plan schema in [Orchestrator Design](../3_design/orchestrator.md) §5 and [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §4, including at minimum `plan_schema_version`, `plan_id`, `generated_at`, `generator` (service version, model identifier, prompt-template version), `applicability` (event type, source system, selected targets), `confidence`, `rationale`, and ordered `steps`.
- **FR-WA-7** Each generated step SHALL include at minimum `step_id`, `type`, `action_id` for `call` steps, `inputs`, and `produces`, and MAY include `condition`, `timeout`, `retry_policy`, `on_failure`, and `metadata`, per [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §4.
- **FR-WA-8** The generated plan SHALL reference the Delivery Targets and the Field Mapping / Field Synthesis / Translation Executor services only as named actions in the plan, not as embedded logic (ADR-0007 hierarchical model). Delivery-target selection SHALL remain outside the delivery-phase plan because that decision is already resolved when this stage runs ([Orchestrator Design](../3_design/orchestrator.md) §5).
- **FR-WA-9** The service SHALL generate steps whose `action_id` values and `type` values are drawn only from its own action registry (ADR-0011 §3). The service SHALL NOT invent actions, raw URLs, Lambda names, queue names, credentials, or arbitrary code.
- **FR-WA-9a** The service SHALL own its action registry directly and SHALL resolve its prompt-time action-registry view internally. The Orchestrator SHALL NOT fetch the action registry and pass it as an input to the service. The same principle applies to the Delivery Targets LLM Decision Service and its own registry.
- **FR-WA-9b** Each entry in the action registry SHALL include an **engineer-authored description** of what that action does. The delivery-phase plan prompt SHALL supply these descriptions to the LLM as context (alongside a generic plan-generation prompt), rather than embedding the full output shape in a single monolithic prompt. These descriptions are authored by engineers and may be revised to improve LLM plan quality. They are distinct from the administrator-authored gating prose (FR-WA-3a) and from admin-authored target descriptions used by the Delivery Targets service.
- **FR-WA-10** Step input bindings SHALL use the declarative source-reference form the Orchestrator resolves (`literal`, `workflow`, `step`), not an arbitrary code or expression language ([Orchestrator Design](../3_design/orchestrator.md) §4; ADR-0011 §5).
- **FR-WA-11** The service SHALL attach a `confidence` and a `rationale` to the gate decision and to the delivery-phase plan, and MAY attach per-step rationale, to satisfy the explainability contract ([POC Requirements](./poc-requirements.md) rationale/confidence; ADR-0007).
- **FR-WA-12** The generated plan artifact SHALL be validated by deterministic rules before it is executed. Structural validity alone SHALL NOT constitute success (see §6). The service SHALL NOT allow an unvalidated plan to flow to execution ([Target POC Requirements](./target-poc-requirements.md) deterministic policy validation; ADR-0007).
- **FR-WA-13** The service SHALL return the full delivery-phase plan artifact inline in the synchronous response. The service SHALL also store the plan artifact and MAY include a `plan_ref` (`plan_id`) in the response for storage correlation. The Orchestrator does not need a second round-trip to retrieve the plan body.
- **FR-WA-14** The service SHALL use a managed model-access adapter consistent with [ADR-0010](../decisions/0010-llm-model-access-strategy.md). For the POC, the primary provider SHALL be Amazon Bedrock via the Converse API.
- **FR-WA-15** The service SHALL support configurable model ID, prompt-template version, and generation parameters without a contract change, independently per stage.
- **FR-WA-16** The service SHALL default to low-temperature generation appropriate for structured, machine-executable plan output.
- **FR-WA-17** The service SHALL support an authoritative evaluation mode in which one request maps to one model attempt and no hidden repair retry occurs, so the POC can measure actual LLM planning capability honestly (ADR-0013).
- **FR-WA-18** If a developer-only repair retry mode is ever added, it SHALL be explicit, opt-in, and separately logged from authoritative evaluation runs.
- **FR-WA-19** The service SHALL record model metadata, prompt-template version, latency, token counts when available, confidence, and rationale in execution logs or stored artifacts for both stages. The immediate response NEED NOT carry all of those fields if a stable log reference is returned (ADR-0010 per-invocation metadata).
- **FR-WA-20** The service SHALL produce plan artifacts with explicit schema/version identifiers so stored plans can be replayed, tested, and compared across prompt or model revisions.

## 6. Validation and Audit Requirements

- **FR-WA-21** Plan validation SHALL be a hard gate ([ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) Layer A). Valid structure is not sufficient. Success SHALL require at minimum:
  - plan-schema validity,
  - `confidence` and `rationale` present,
  - every step's `action_id` and `type` present in the service's action registry,
  - and every step input binding resolvable (its `workflow` paths and referenced prior-step `step_id` values exist and are produced before use).
- **FR-WA-22** Whether the generated plan includes the expected steps for a given applicability (for example, LearnCard profile resolution, issuer-payload mapping, issuance, and wallet delivery for the POC LearnCard path) SHALL be evaluated in the **test harness / unit test layer**, not enforced as a hard service validation gate. Requiring specific step presence as a hard gate risks the service "cheating" by satisfying the validator rather than producing a genuinely good plan. The test harness (Layer B, ADR-0013 / ADR-0021) is the right place to assert which steps should appear, consistent with [Orchestrator Design](../3_design/orchestrator.md) §5 and [FR-OR-12/14/15](./orchestrator.md).
- **FR-WA-23** The service SHALL NOT silently fall back to a hand-authored deterministic plan when the model output is bad. Invalid outputs SHALL be stored as failed plan artifacts or failed invocation records with their validation errors attached, so they remain evidence for prompt tuning without being reusable as successful plans.
- **FR-WA-24** The service SHALL record which prompt template and model produced each gate decision and each plan so prompt or model changes can be compared later against the frozen [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) evaluation corpus.
- **FR-WA-25** The service's Layer B capability evaluation against the frozen ADR-0013 corpus SHALL be implemented using the shared DeepEval test harness ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)) as a deterministic comparator: the gate decision matched against the scenario's canonical terminal outcome, and the plan matched against the canonical expected plan for the scenario, including required or forbidden major steps (ADR-0013 Layer B, Workflow Actions row).
- **FR-WA-26** The service SHALL screen free-text values drawn from the event and context bundle for prompt-injection attempts before they are included in a Bedrock prompt ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)).
- **FR-WA-27** The service SHALL NOT claim success based only on syntactically valid JSON. Action-registry conformance and binding resolvability are hard structural gates (FR-WA-21). Whether certain steps are present under certain conditions is evaluated in the test harness (FR-WA-22), not enforced as a hard gate here.

## 7. Reusable Plans

- **FR-WA-28** Only delivery-phase plans SHALL be eligible for the reusable-plan store, keyed by applicability (at minimum event type, source system, and selected targets), consistent with [ADR-0009](../decisions/0009-workflow-actions-orchestration-model.md) "Artifact reuse," [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) §8, and [FR-OR-28/29](./orchestrator.md). Pre-target gate decisions SHALL NOT be stored for reuse.
- **FR-WA-29** The service SHALL support fresh generation without reuse as the default POC evaluation path, and SHALL persist generated plans even when reuse is bypassed on read (ADR-0014 "skip lookup/reuse on read"). Reuse lookup itself is controlled by the Orchestrator ([FR-OR-28](./orchestrator.md)); the service is invoked to regenerate when lookup is disabled, misses, or a stored plan fails validation ([Orchestrator Design](../3_design/orchestrator.md) §8).

## 8. Phase-1 vs Later

- **FR-WA-30** In Phase 1, both stages of this service are satisfied by deterministic Orchestrator stubs, not by this LLM service: the pre-target stub returns `continue` for the supported happy-path events, and the delivery-phase stub returns a fixed plan sequence for the selected targets ([Orchestrator Design](../3_design/orchestrator.md) §2/§6; [FR-OR-5/10/12](./orchestrator.md)). This LLM service replaces those stubs behind the same two planner seams without changing the executor or the plan/gate contracts.
- **FR-WA-31** The service SHALL preserve the same logical gate and plan contracts across Phase 1 stubs, local live mode, and AWS deployment, so the Orchestrator does not need separate integration paths.

## 9. Local vs AWS Requirements

- **FR-WA-32** For local development, the service SHALL support a live Bedrock-backed mode so prompt and model iteration can happen against the same provider used in AWS.
- **FR-WA-33** Local live mode SHALL rely on the normal AWS SDK credential chain rather than hard-coded credentials, consistent with [ADR-0010](../decisions/0010-llm-model-access-strategy.md).
- **FR-WA-34** For local automated tests and offline development, the service SHALL support a deterministic replay or stub mode that does not require live Bedrock access and preserves the same request/response contracts as live mode.
- **FR-WA-35** For the AWS-shaped deployment target, the service SHALL be callable through the same logical two-stage boundary from the Orchestrator whether hosted as a standalone Lambda-sized service or as a dedicated handler inside a shared LLM-decision runtime ([FR-OR-32](./orchestrator.md)), and SHALL use AWS IAM-based access to Bedrock rather than application-managed API keys.

## 10. Out of Scope

The Workflow Actions LLM Decision Service does not need to provide:

- executing the plan or persisting execution state,
- delivery-target selection, mapping JSONata generation, or synthesized field text,
- a separate **Policy Rules Service** — the structural validation in §6 is this service's own output validation; the Policy Rules Service that the Orchestrator would call between plan generation and execution (ADR-0011 §2, ADR-0007) is out of POC scope and is distinct from that structural validation,
- arbitrary mid-flight replanning after delivery-phase execution has begun (ADR-0011 §10),
- human-in-the-loop plan refinement,
- or automatic fine-tuning or custom model training.

## 11. Open Questions

- **Gate decision schema — named terminate outcomes.** The gate decision fields (`decision` / `confidence` / `rationale`) are defined in [Design §2 / §4](../3_design/workflow-actions-llm-decision-service.md). The exact set of named `terminate_*` outcome strings is not yet fixed; new outcomes can be added without a contract change.
- **Applicability key dimensions (ADR-0009 / ADR-0011 Open Questions).** Which dimensions beyond event type, source system, and selected targets belong in the delivery-phase plan applicability key is still open.
- **Confidence semantics.** ADR-0007 leaves per-service confidence thresholds unresolved; acceptable gate and plan confidence thresholds for this service are deferred to the evaluation harness (ADR-0013), not fixed here.
- **Policy Rules rule set.** ADR-0011 §2 places Policy Rules validation between plan generation and execution, but no Policy Rules service design exists yet in this repo, so the exact rule set that validates a plan is stated intent, not a verified contract. The Policy Rules Service itself is out of POC scope (§10).
