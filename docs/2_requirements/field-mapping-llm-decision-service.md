# Field Mapping LLM Decision Service Requirements

Status: Draft
Date: 2026-06-25
Related: [Requirements overview](./README.md) · [Target POC Requirements](./target-poc-requirements.md) · [Design](../3_design/field-mapping-llm-decision-service.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [ADR-0005](../decisions/0005-schema-mapping-language.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Purpose

The **Field Mapping LLM Decision Service** generates the mapping artifact for one **transformation phase** from ADR-0017. Its job is to determine how the declared source artifacts for that phase should populate the target schema, and to express that decision as:

- ready-to-run JSONata for fields that can map directly,
- synthesis placeholders for fields that require AI synthesis,
- and a separate synthesis-request artifact for those placeholder-backed fields.

The primary POC question for this service is whether an LLM can do this mapping job reliably enough to justify the architecture. The service should therefore keep the mapping decision visible and auditable, not hide it inside downstream Python code or delivery adapters.

## 2. Responsibilities

The Field Mapping LLM Decision Service is responsible for:

- accepting one mapping request for one transformation phase,
- loading the source and target field catalogs or data dictionaries referenced by that request,
- determining which target fields are `direct` and which are `synthesis`,
- generating JSONata that is ready for deterministic execution,
- generating placeholder-backed synthesis requests for fields that require synthesis,
- storing the mapping artifact and any synthesis-request artifact for downstream reuse,
- and returning a compact response that tells the Orchestrator where those stored artifacts can be found.

The service is not responsible for:

- selecting delivery targets,
- generating final synthesized field text,
- executing JSONata,
- fetching live LMS resources directly from source systems,
- issuing or delivering badges,
- or making policy decisions.

## 3. Transformation Types

Per ADR-0017, the default expected transformation path for the POC has three transformation phases. The Field Mapping service contract should identify the current problem using `transformation_type`, because the Workflow Actions service may decide which transformations occur and in what order.

The service should accept exactly one of these `transformation_type` values per request:

| `transformation_type` | Primary source artifacts | Target |
| --- | --- | --- |
| `credential_template` | LMS learning-context artifacts for the achievement definition | Credential-template schema |
| `issuer_payload` | Learner-specific LMS artifacts plus the stored credential template and any issuer-required execution context | Issuer target schema / unsigned badge issuance payload |
| `wallet_payload` | Issued badge artifact plus any wallet-delivery-specific execution context | Wallet target schema / wallet delivery payload |

The Field Mapping request should name the transformation explicitly because the available source fields, target schema, and reuse keys differ across these three cases.

## 4. Inputs and Outputs

### Request inputs

The request should provide the current transformation's source payloads inline by default so they can stay transient inside the workflow execution. Reference-based loading is still acceptable as a fallback when a payload is already materialized elsewhere or is too large to pass inline.

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Tie the request to one workflow execution and its logs |
| `transformation_type` | Identifies which of the three transformation problems is being mapped |
| `source_system` | Identifies the upstream system whose field catalog applies to the source payloads |
| `context_profile_id` | Identifies the deterministic Context Builder fetch profile that produced the source payload shape for this request |
| `delivery_target` | Identifies the downstream target context for this transformation |
| Source payload set | Carries the already-prepared transient source payloads for the current transformation |

Prompt templates, model IDs, temperatures, and other LLM runtime settings are configuration of the service runtime. They are not primary business inputs in the same sense as source artifacts and target schemas.

The Field Mapping service itself should resolve the appropriate source and target catalogs or data dictionaries from its own configuration and storage using `source_system`, `context_profile_id`, `delivery_target`, and `transformation_type`.

Building the source-resource catalog files, target catalog files, and context-profile mapping files that the service depends on is within the development scope of this service. These catalog files do not pre-exist and must be authored as part of building and testing this service. Source-resource catalog files describe the field shapes of the Mock LMS Canvas-style endpoints. Target catalog files describe the field shapes of the downstream delivery-target schemas. Context-profile mapping files link a `source_system + context_profile_id` to the set of source-resource catalogs that apply for that fetch profile.

### Request inputs by transformation type

| `transformation_type` | Required source payloads |
| --- | --- |
| `credential_template` | Learning-context payload |
| `issuer_payload` | Learner-context payload; credential-template payload; any issuer-specific execution payloads |
| `wallet_payload` | Issued-badge payload; any wallet-delivery-context payloads |

If the service uses external skills-framework grounding, that grounding should come from service-managed configuration or retrieval behavior, not from the Orchestrator inlining the full framework content into the request payload.

### Outputs

The synchronous service response should be compact. The full mapping artifact should be stored immediately and referred to by identifier.

| Output | Purpose |
| --- | --- |
| `mapping_artifact_ref` | Points to the stored JSONata mapping artifact |
| `synthesis_request_ref` or `null` | Points to the stored synthesis-request artifact when synthesis is required |
| `requires_synthesis` | Tells the Orchestrator whether the Field Synthesis step is needed for this transformation |
| `llm_invocation_log_ref` | Lets the Orchestrator correlate to detailed invocation metadata in execution logs |
| Terminal status / failure details | Tells the Orchestrator whether the mapping step succeeded |

The full stored mapping artifact should contain the actual JSONata and placeholder structure needed by downstream execution. Detailed model metadata such as token counts, latency, confidence, and rationale belong in stored logs or artifacts, not necessarily in the immediate runtime response.

## 5. Functional Requirements

- **FR-FM-1** The service SHALL accept one request per transformation phase invocation rather than combining multiple transformation phases into one call.
- **FR-FM-2** The request SHALL identify `transformation_type` explicitly as one of:
  - `credential_template`
  - `issuer_payload`
  - `wallet_payload`
- **FR-FM-3** The request SHALL identify the source system, the Context Builder `context_profile_id` that produced the source payload shape, and the selected delivery target for the current transformation.
- **FR-FM-4** The request SHALL provide the source payloads needed for the selected `transformation_type` inline by default. The service SHALL NOT fetch live LMS resources directly from upstream systems.
- **FR-FM-5** The service SHALL resolve the applicable source field catalog or source data dictionary, and the applicable target schema or target field catalog, from its own configuration and storage using the request's system and transformation identifiers.
- **FR-FM-5a** The implementation of this service SHALL include authoring the committed source-resource catalog files (OpenAPI 3.1 files built from the Mock LMS Canvas-style endpoint schemas), target catalog files (built from the delivery-target schemas such as the LearnCard SDK `UnsignedVC` shape), and context-profile mapping files (derived from the Context Builder fetch profiles defined in the Context Builder design). These catalog files are an explicit deliverable of the development effort for this service, not pre-existing inputs.
- **FR-FM-6** The service SHALL support only two mapping classifications:
  - `direct`
  - `synthesis`
- **FR-FM-7** `direct` SHALL mean direct mapping from one or more source artifact fields available in the current transformation's source payload set. Mapping directly from a credential-template field or directly from an issued-badge field is still `direct`.
- **FR-FM-8** The primary stored mapping artifact SHALL be executable JSONata ready for the deterministic Transformation Executor to run.
- **FR-FM-9** For fields that require synthesis, the stored mapping artifact SHALL include synthesis placeholders that the deterministic executor can resolve later.
- **FR-FM-10** For fields that require synthesis, the service SHALL also produce a separate synthesis-request artifact containing enough information for the Field Synthesis service to know:
  - which placeholder is being filled,
  - which target field is being satisfied,
  - what source subset should be used,
  - and what field-specific synthesis instruction applies.
- **FR-FM-11** The service SHALL NOT generate final synthesized text. That work belongs to the Field Synthesis LLM Decision Service.
- **FR-FM-12** The service SHALL NOT execute JSONata. That work belongs to the deterministic Transformation Executor.
- **FR-FM-13** The service SHALL store the generated mapping artifact immediately and SHALL return a reference to it in the synchronous response. Returning the full JSONata inline MAY be supported for local debugging but SHALL NOT be the normal downstream contract.
- **FR-FM-14** The service SHALL validate the generated artifact before reporting success. Successful output SHALL require:
  - response-schema validity,
  - valid JSONata parse for executable expressions,
  - valid placeholder structure for synthesis-backed fields,
  - generated JSONata that references only fields available in the supplied source payload set,
  - and generated output structure that is valid for the requested target schema.
- **FR-FM-15** The service SHALL use a managed model-access adapter consistent with ADR-0010. For the POC, the primary provider SHALL be Amazon Bedrock.
- **FR-FM-16** The service SHALL support configurable model ID, prompt-template version, and generation parameters without requiring a contract change.
- **FR-FM-17** The service SHALL default to low-temperature generation appropriate for machine-executable structured output.
- **FR-FM-18** The service SHALL support an authoritative evaluation mode in which one request maps to one model attempt and no hidden repair retry occurs, so the POC can measure actual LLM capability honestly.
- **FR-FM-19** If a developer-only repair retry mode is ever added, it SHALL be explicit, opt-in, and separately logged from authoritative evaluation runs.
- **FR-FM-20** The service SHALL record model metadata, prompt-template version, latency, token counts when available, confidence, and rationale in execution logs or stored artifacts. The immediate response to the Orchestrator NEED NOT carry all of those fields if a stable log reference is returned.
- **FR-FM-21** The service SHALL produce artifacts with explicit schema/version identifiers so stored mappings can be replayed, tested, and compared across prompt or model revisions.

## 6. Validation and Audit Requirements

- **FR-FM-22** The service SHALL make it possible to tell which fields require synthesis, even if the runtime payload does not carry an explicit separate classification field for every target field. That distinction MAY be implicit in the stored JSONata plus placeholder structure.
- **FR-FM-23** The service MAY record extra field-level mapping metadata for testing and debugging, but that extra metadata SHALL NOT be required in the compact runtime contract if it merely duplicates what is already implicit in the stored artifact.
- **FR-FM-24** The service SHALL record which prompt template and model produced each mapping artifact so prompt or model changes can be compared later against the frozen evaluation corpus from ADR-0013.
- **FR-FM-25** The service SHALL support uncached evaluation runs and SHALL default to uncached generation for POC evaluation and test-oriented development.
- **FR-FM-26** The service SHALL support a configuration switch that enables stored mapping reuse for production-like behavior once the team wants to exercise that path.
- **FR-FM-27** The service SHALL NOT claim success based only on syntactically valid JSON. JSONata validity and placeholder-structure validity are hard gates for the service.

## 7. Local vs AWS Requirements

- **FR-FM-28** For local development, the service SHALL support a live Bedrock-backed mode so prompt and model iteration can happen against the same provider used in AWS.
- **FR-FM-29** Local live mode SHALL rely on the normal AWS SDK credential chain rather than hard-coded credentials. Developer configuration MAY come from environment variables, shared AWS config files, or an explicitly selected AWS profile.
- **FR-FM-30** Local live mode SHALL require that the developer's AWS identity has the Bedrock inference permission needed for the chosen model and that the model has been enabled for the relevant account and region.
- **FR-FM-31** For local automated tests and offline development, the service SHALL support a deterministic replay or stub mode that does not require live Bedrock access.
- **FR-FM-32** Replay or stub mode SHALL preserve the same logical request and response contracts used by live mode so the Orchestrator and downstream steps do not need separate integration code paths.
- **FR-FM-33** For the AWS-shaped deployment target, the service SHALL be callable through the same logical boundary from the Orchestrator whether it is hosted as a standalone Lambda-sized service or as a dedicated handler inside a shared LLM-decision runtime.
- **FR-FM-34** For the AWS-shaped deployment target, the live service SHALL use AWS IAM-based access to Bedrock rather than application-managed third-party API keys.

## 8. Out of Scope

The Field Mapping LLM Decision Service does not need to provide:

- multi-turn human-in-the-loop prompt refinement,
- automatic fine-tuning or custom model training,
- target selection or workflow planning,
- direct source-system reads from LMS or skills-framework endpoints,
- or final payload delivery.
