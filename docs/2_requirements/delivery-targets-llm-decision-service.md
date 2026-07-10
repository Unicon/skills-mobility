# Delivery Targets LLM Decision Service Requirements

Status: Draft
Date: 2026-07-10
Related: [Requirements overview](./README.md) · [Target POC Requirements](./target-poc-requirements.md) · [Design](../3_design/delivery-targets-llm-decision-service.md) · [Field Mapping Requirements](./field-mapping-llm-decision-service.md) · [Workflow Actions Requirements](./workflow-actions-llm-decision-service.md) · [Orchestrator Design](../3_design/orchestrator.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Purpose

The **Delivery Targets LLM Decision Service** is the first of ADR-0007's three LLM Decision Services. Its job is described in [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) as **"selecting which downstream systems should receive transformed data for this event."** It reasons over event type, learner context, policy context, and the set of available delivery targets to produce a small set of selected targets, each with a confidence score and a rationale.

Compared to the Field Mapping service, this is a **routing and eligibility decision**, not a structural translation task. Per [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md), "delivery target selection is primarily a routing and eligibility decision … the prompt is relatively stable and the output schema is simple." Per [ADR-0010](../decisions/0010-llm-model-access-strategy.md) §24, "the output schema is relatively constrained: a small set of selected targets with confidence and rationale." This service therefore uses a simpler prompt and a smaller output schema than Field Mapping.

The primary POC question for this service is whether an LLM can make the routing decision reliably enough — and explainably enough — to justify replacing the deterministic stub that selects targets today. The service should therefore keep the selection decision visible and auditable, and it must never let the LLM's selection flow straight to delivery without deterministic validation against the eligible target set.

## 2. Responsibilities

The Delivery Targets LLM Decision Service is responsible for:

- accepting one delivery-target selection request for one workflow execution,
- loading the available-delivery-targets catalog that enumerates the targets the POC supports,
- reasoning over event type, learner context, and policy context to select a subset of those targets,
- assigning each selected target a confidence score and a rationale,
- deterministically validating the LLM's selection against the available/eligible target set before reporting success,
- storing the selection artifact and its invocation metadata for downstream reuse and audit,
- and returning a compact response the Orchestrator can pass to the delivery-phase Workflow Actions call.

The service is not responsible for:

- generating transformation mappings or field synthesis,
- generating the workflow plan or deciding workflow order,
- executing delivery or calling delivery adapters,
- fetching live LMS resources directly from source systems,
- or deciding whether the workflow should proceed at all (that is the pre-target Workflow Actions gate, which runs first — see [Orchestrator Design](../3_design/orchestrator.md) §3).

## 3. Available Delivery Targets

Per [ADR-0016](../decisions/0016-delivery-routing-topology.md), the POC's delivery layer exposes a stable envelope plus versioned action-specific payload schemas, with each delivery action dispatched to a dedicated adapter. The available delivery targets this service selects among are:

| Delivery target | Delivery action (ADR-0016) | Adapter | Runtime |
| --- | --- | --- | --- |
| `learncard_issuer` | `issue_learncard_badge` | LearnCard Issuer Adapter | Node/TypeScript |
| `learncard_wallet` | `deliver_to_learncard_wallet` | LearnCard Wallet Adapter | Python |
| `smart_resume` | `deliver_to_smartresume` | SmartResume Wallet Adapter | Python |

These three targets are the available target set for the POC. The service selects a subset of them per event; it does not invent targets outside this catalog. As with Field Mapping's catalogs, the **available-delivery-targets catalog is a committed artifact this service resolves** — it does not pre-exist and must be authored as part of building this service (see FR-DT-5a).

> Open question: ADR-0016 defines the delivery-action-to-adapter topology but does not itself define per-target *eligibility* attributes (for example, which event types or learner-profile states make a target eligible). The catalog contents that express eligibility to the model, and how much eligibility is deterministic policy versus LLM judgment, are open (see §6).

## 4. Inputs and Outputs

### Request inputs

The request should provide the decision context inline by default so it can stay transient inside the workflow execution, consistent with how the Orchestrator passes the Context Builder bundle (see [Orchestrator Design](../3_design/orchestrator.md) §4).

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Tie the request to one workflow execution and its logs |
| `event_type` | The learner/credential event driving the decision (e.g. `skill_mastered`) |
| `source_system` | Identifies the upstream system that produced the event |
| Learner context | Learner-specific decision context assembled by the Context Builder |
| Policy context | Policy/eligibility context assembled by the Context Builder |

Per ADR-0007, the key inputs for this decision are **event type, learner context, policy context, and available delivery targets**. The available delivery targets are resolved by the service from its own catalog (§3, FR-DT-5), not supplied by the Orchestrator. Prompt templates, model IDs, temperatures, and other LLM runtime settings are configuration of the service runtime, not primary business inputs.

The service should treat the learner and policy context as **opaque JSON** from the Context Builder bundle where practical, consistent with the Orchestrator's handling of that bundle ([Orchestrator Design](../3_design/orchestrator.md) §4), rather than requiring an exhaustive typed model of the full context up front.

### Outputs

The synchronous service response should be compact. The full selection artifact should be stored immediately and referred to by identifier.

| Output | Purpose |
| --- | --- |
| `selection_artifact_ref` | Points to the stored selection artifact (selected targets + per-target confidence and rationale) |
| `selected_targets` | The validated set of selected delivery-target identifiers, for direct use by the delivery-phase Workflow Actions call |
| `llm_invocation_log_ref` | Lets the Orchestrator correlate to detailed invocation metadata in execution logs |
| Terminal status / failure details | Tells the Orchestrator whether the selection step succeeded |

The full stored selection artifact carries the per-target confidence and rationale. Detailed model metadata such as token counts, latency, and prompt-template version belong in stored logs or artifacts, not necessarily in the immediate runtime response.

## 5. Functional Requirements

- **FR-DT-1** The service SHALL accept one delivery-target selection request per workflow execution invocation.
- **FR-DT-2** The request SHALL identify `event_type` and `source_system`, and SHALL carry the learner context and policy context needed for the routing decision.
- **FR-DT-3** The service SHALL NOT fetch live LMS resources directly from upstream systems; it SHALL rely on the context supplied in the request (assembled deterministically by the Context Builder).
- **FR-DT-4** The service SHALL select a subset of the available delivery targets. Its output SHALL NOT include any target that is not present in the available-delivery-targets catalog.
- **FR-DT-5** The service SHALL resolve the available-delivery-targets catalog from its own configuration and storage rather than requiring the Orchestrator to enumerate targets in the request.
- **FR-DT-5a** The implementation of this service SHALL include authoring the committed available-delivery-targets catalog file. For the POC the catalog SHALL enumerate `learncard_issuer`, `learncard_wallet`, and `smart_resume` per [ADR-0016](../decisions/0016-delivery-routing-topology.md), with a human-readable description of each target sufficient to explain the routing choice to the model. This catalog file does not pre-exist and is an explicit deliverable of the development effort for this service, not a pre-existing input.
- **FR-DT-6** Each selected target in the output SHALL carry a `confidence` score and a `rationale`, consistent with [ADR-0010](../decisions/0010-llm-model-access-strategy.md) §165 (confidence and rationale as structured output).
- **FR-DT-7** The service SHALL express the LLM decision as a **schema-constrained structured response**. It SHALL NOT rely on free-form text parsing to recover the selected targets.
- **FR-DT-8** The service SHALL store the selection artifact immediately and SHALL return a reference to it in the synchronous response. Returning the full artifact inline MAY be supported for local debugging but SHALL NOT be the normal downstream contract.
- **FR-DT-9** The service SHALL run **before** the Transformation Mappings (Field Mapping) service, per the hard dependency in [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md): the mapping instructions depend on which targets have been selected.
- **FR-DT-10** The service SHALL be invocable as a named step in the Orchestrator's runtime shape — the `select_delivery_targets` seam that sits between the pre-target Workflow Actions gate and the delivery-phase Workflow Actions plan (see [Orchestrator Design](../3_design/orchestrator.md) §3, §6).
- **FR-DT-11** The service SHALL use a managed model-access adapter consistent with [ADR-0010](../decisions/0010-llm-model-access-strategy.md). For the POC, the primary provider SHALL be Amazon Bedrock, invoked through the Converse API.
- **FR-DT-12** The service SHALL support configurable model ID, prompt-template version, and generation parameters without requiring a contract change.
- **FR-DT-13** The service SHALL default to low-temperature generation appropriate for a stable, reproducible routing decision.
- **FR-DT-14** The service SHALL support an authoritative evaluation mode in which one request maps to one model attempt and no hidden repair retry occurs, so the POC can measure actual LLM routing capability honestly.
- **FR-DT-15** If a developer-only repair retry mode is ever added, it SHALL be explicit, opt-in, and separately logged from authoritative evaluation runs.
- **FR-DT-16** The service SHALL record model metadata, prompt-template version, latency, token counts when available, and the per-target confidence and rationale in execution logs or stored artifacts. The immediate response to the Orchestrator NEED NOT carry all of those fields if a stable log reference is returned.
- **FR-DT-17** The service SHALL produce artifacts with explicit schema/version identifiers so stored selections can be replayed, tested, and compared across prompt or model revisions.

## 6. Validation and Audit Requirements

The repo-wide architectural contract is that **LLM reasoning is always paired with deterministic policy validation and complete audit logging** ([Target POC Requirements](./target-poc-requirements.md) §5: "LLM output MUST NOT flow directly to downstream delivery without deterministic validation"). This service must honor that contract for its own output.

- **FR-DT-18** The service SHALL deterministically validate the LLM's selection **before reporting success**. Successful output SHALL require:
  - response-schema validity,
  - every selected target present in the available-delivery-targets catalog,
  - no duplicate targets in the selection,
  - a non-empty selection unless the empty selection is an explicitly allowed outcome (see open question below),
  - and presence of `confidence` and `rationale` for each selected target.
- **FR-DT-19** This deterministic validation of the selection against the available/eligible target set is a **hard gate** (ADR-0013 Layer A). The service SHALL NOT let an unvalidated LLM selection flow downstream to the delivery-phase plan or delivery layer.
- **FR-DT-20** The service SHALL NOT claim success based only on syntactically valid JSON. Membership in the available/eligible target set is a hard gate, not a preference.
- **FR-DT-21** Invalid selections SHALL still be stored as **failed artifacts** or failed invocation records with their validation errors attached, as evidence for prompt tuning and model comparison. They SHALL NOT be reusable as successful selection artifacts.
- **FR-DT-22** The service SHALL record which prompt template and model produced each selection so prompt or model changes can be compared later against the frozen evaluation corpus from [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md).
- **FR-DT-23** The service's Layer B capability evaluation against the frozen ADR-0013 corpus SHALL be implemented using the shared DeepEval test harness ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)). Because target selection compares a produced set against a canonical expected set, this is expected to be a deterministic custom metric (set correctness), not an LLM-as-judge metric.
- **FR-DT-24** The service SHALL screen free-text values in the supplied learner and policy context for prompt-injection attempts before they are included in a Bedrock prompt ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)).
- **FR-DT-25** The service SHALL support uncached evaluation runs and SHALL default to uncached generation for POC evaluation and test-oriented development.
- **FR-DT-26** The service MAY support a configuration switch that enables stored-selection reuse for production-like behavior once the team wants to exercise that path; reuse SHALL be opt-in, not the default evaluation path.

> Open question: whether an **empty selection** ("no eligible target for this event") is a valid successful outcome, or whether it should be treated as a failure or routed back to the pre-target gate, is not settled by the source ADRs and is left open. ADR-0007's fifth Open Question ("Should all three services be invoked for every event, or should some be conditionally invoked?") is the relevant upstream uncertainty.

> Open question: ADR-0007's Open Questions also ask "How should inter-service failures be handled? If Delivery Targets fails or returns low-confidence results, should Transformation Mappings be blocked or should it proceed with a fallback set of targets?" This is not resolved here; a low-confidence or failed selection's downstream effect is deferred to the orchestration/policy design.

## 7. Local vs AWS Requirements

- **FR-DT-27** For local development, the service SHALL support a live Bedrock-backed mode so prompt and model iteration can happen against the same provider used in AWS.
- **FR-DT-28** Local live mode SHALL rely on the normal AWS SDK credential chain rather than hard-coded credentials. Developer configuration MAY come from environment variables, shared AWS config files, or an explicitly selected AWS profile.
- **FR-DT-29** Local live mode SHALL require that the developer's AWS identity has the Bedrock inference permission needed for the chosen model and that the model has been enabled for the relevant account and region.
- **FR-DT-30** For local automated tests and offline development, the service SHALL support a deterministic replay or stub mode that does not require live Bedrock access.
- **FR-DT-31** Replay or stub mode SHALL preserve the same logical request and response contracts used by live mode so the Orchestrator and downstream steps do not need separate integration code paths.
- **FR-DT-32** For the AWS-shaped deployment target, the service SHALL be callable through the same logical boundary from the Orchestrator whether it is hosted as a standalone Lambda-sized service or as a dedicated handler inside a shared LLM-decision runtime.
- **FR-DT-33** For the AWS-shaped deployment target, the live service SHALL use AWS IAM-based access to Bedrock rather than application-managed third-party API keys.

## 8. POC Phasing

Per [Orchestrator Design](../3_design/orchestrator.md) §2 and §6, delivery-target selection today is a **deterministic stub** at the `select_delivery_targets` seam that always selects `[learncard_issuer, learncard_wallet]`. This service is the target-POC implementation that replaces that stub at the same seam.

- **FR-DT-34** The service SHALL replace the deterministic `select_delivery_targets` stub at the existing Orchestrator seam without requiring the executor to change its step-dispatch contract; the change from stub to LLM service SHALL be a step-implementation change, not an executor rewrite.
- **FR-DT-35** The Phase 1 behavior (always select `[learncard_issuer, learncard_wallet]`) SHALL remain available as the deterministic replay/stub mode (FR-DT-30) so the end-to-end slice can run without live Bedrock access.

## 9. Out of Scope

The Delivery Targets LLM Decision Service does not need to provide:

- multi-turn human-in-the-loop prompt refinement,
- automatic fine-tuning or custom model training,
- transformation mapping, field synthesis, or workflow planning,
- direct source-system reads from LMS endpoints,
- delivery execution or adapter dispatch (owned by the Delivery Router per [ADR-0016](../decisions/0016-delivery-routing-topology.md)),
- or the deterministic pre-target gate decision (owned by the Workflow Actions service).
