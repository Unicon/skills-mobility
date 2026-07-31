# Field Synthesis LLM Decision Service Requirements

Status: Draft
Date: 2026-07-16
Related: [Requirements overview](./README.md) · [Target POC Requirements](./target-poc-requirements.md) · [Design](../3_design/field-synthesis-llm-decision-service.md) · [POC Component Boundary Matrix](../3_design/poc-component-boundaries.md) · [Field Mapping Requirements](./field-mapping-llm-decision-service.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Purpose

The **Field Synthesis LLM Decision Service** generates the human-facing natural-language text values for credential fields that the Field Mapping LLM Decision Service has identified as requiring synthesis. Its job is to answer one question for each synthesis placeholder it receives:

`What should this human-facing field say, given only the source material the mapping service identified for it?`

Field Mapping determines which fields require synthesis and produces targeted synthesis briefs for them. Field Synthesis consumes those briefs and generates the actual text. The two services are siblings in the same transformation pipeline, each invoked per synthesis-bearing transformation phase per ADR-0017. The primary POC question for this service is whether an LLM can generate grounded, useful, human-facing credential content from learner and course data reliably enough to justify its place in the architecture.

## 2. Responsibilities

The Field Synthesis LLM Decision Service is responsible for:

- accepting one synthesis request per transformation-loop invocation, containing one or more synthesis briefs produced by the Field Mapping service,
- generating a human-facing text value for each requested placeholder,
- ensuring that every generated value is grounded in and derived from the source material supplied in the brief for that placeholder,
- returning a flat map of generated values keyed by `placeholder_id` inline in the synchronous response,
- storing the synthesis result artifact and returning a storage-correlation reference alongside the inline values,
- and recording invocation metadata per ADR-0010 ("Decision").

The service is not responsible for:

- deciding which fields require synthesis — that determination belongs to the Field Mapping LLM Decision Service,
- generating JSONata mappings or executing them,
- fetching source data from LMS or other upstream systems,
- selecting delivery targets,
- issuing or delivering credentials,
- or making policy decisions.

## 3. Transformation Context

Per ADR-0017, the default expected transformation path has three sequential phases (`credential_template` → `issuer_payload` → `wallet_payload`). Field Synthesis is **phase-specific, not universally mandatory**: it is invoked only in phases whose Field Mapping result carries synthesis placeholders. In the default POC path:

- **`credential_template` (credential-level):** generates text for credential-level synthesis fields, such as an achievement description or an alignment rationale for a skills-framework competency — values that are the same for every learner who earns the same credential from the same learning context.
- **`issuer_payload` (learner-level):** generates text for learner-level synthesis fields, such as a summary of the assignment that demonstrated the specific learner's skill mastery.
- **`wallet_payload`:** usually purely structural; skips synthesis when the wallet target schema needs no synthesized fields (no synthesis-request artifact is produced, so this service is not invoked).

The same service handles every invocation — up to three per first-seen execution — with no phase-specific variants. The distinction between the credential-level and learner-level synthesis tasks is entirely in the synthesis briefs the Field Mapping service produces for each phase.

## 4. Inputs and Outputs

### Request inputs

The primary input is the synthesis-request artifact produced by the Field Mapping service. That artifact carries one entry per placeholder, each containing a targeted source-data brief. The service does not need to resolve catalogs, fetch source data, or determine which fields to synthesize.

| Input | Purpose |
| --- | --- |
| `execution_id` and correlated identifiers | Ties the request to one workflow execution and its logs |
| `transformation_type` | Identifies which transformation loop this synthesis request belongs to |
| `synthesis_request_ref` or inline synthesis request | The synthesis-request artifact produced by Field Mapping, either as a storage reference or inlined for local development |
| Each brief's `placeholder_id` | Identifies which placeholder the generated text will satisfy |
| Each brief's `instruction` | Field-specific guidance on length, tone, or framing for the generated value |
| Each brief's `source_payloads` and/or `source_payload_paths` | The targeted source-data snapshot for that specific placeholder |

The synthesis request is an **array of per-placeholder brief objects**. Abbreviated structural sketch:

```json
{
  "synthesis_request_ref": "synthesis:<stable_key>",
  "requests": [
    { "placeholder_id": "...", "instruction": "...", "source_payloads": { "...": "..." } },
    { "placeholder_id": "...", "instruction": "...", "source_payloads": { "...": "..." } }
  ]
}
```

The full brief shape (including `target_path` and `source_payload_paths`) is defined in the design (§5). The point here is that `requests` is an array: one element per placeholder, each self-contained.

Prompt templates, model IDs, temperatures, and other LLM runtime settings are service configuration. They are not business inputs on the request.

### Outputs

The synchronous service response is compact and returns generated content inline:

| Output | Delivery |
| --- | --- |
| `values` | **Inline always** — flat `{ "<placeholder_id>": "<text>" }` map of every generated value |
| `confidence` | **Inline always** — model-reported confidence score |
| `rationale` | **Inline always** — model-reported explanation of the synthesis decision |
| `synthesis_result_ref` | Optional storage-correlation pointer; lets the Orchestrator or Transformation Executor locate the persisted artifact when needed |
| `llm_invocation_log_ref` | Log-only — lets the Orchestrator correlate to detailed invocation metadata in execution logs |
| Terminal status / failure details | Tells the Orchestrator whether synthesis succeeded |

`values`, `confidence`, and `rationale` are always present in the synchronous response; they are not withheld behind a ref. Detailed model metadata (token counts, latency, model ID) belongs in stored logs, not the immediate runtime response.

## 5. Functional Requirements

- **FR-FS-1** The service SHALL accept one synthesis request per transformation-loop invocation. One invocation covers all placeholders from one Field Mapping loop result.
- **FR-FS-2** The request SHALL carry a `transformation_type` identifying the current transformation phase (ADR-0017): `credential_template` for the credential-level phase or `issuer_payload` for the learner-level phase. Field Synthesis is phase-specific — the `wallet_payload` phase is normally purely structural and produces no synthesis request (see §8).
- **FR-FS-3** The synthesis request SHALL supply one brief per placeholder. Each brief SHALL include the `placeholder_id`, the `instruction`, and at least one of: an explicit `source_payloads` snapshot or `source_payload_paths` references into the source payload set.
- **FR-FS-4** The service SHALL NOT fetch source data from LMS or other upstream systems. All source material for each placeholder arrives in the synthesis brief.
- **FR-FS-5** The service SHALL generate a text value for every `placeholder_id` present in the synthesis request. No placeholder SHALL be left without a corresponding value in the result. No value SHALL be returned for a `placeholder_id` not present in the request.
- **FR-FS-6** Each generated value SHALL be grounded only in the source material supplied in the brief for that placeholder. The model SHALL NOT introduce facts, entities, or claims that are not present in or inferable from the supplied source content.
- **FR-FS-7** The service SHALL respect the `instruction` field in each brief. The `instruction` may specify constraints on length, tone, target audience, or field-specific framing for the generated text.
- **FR-FS-8** The service SHALL NOT generate JSONata, synthesis placeholders, or any machine-executable artifact. Text generation is its only output.
- **FR-FS-9** The service SHALL store the synthesis result artifact immediately, SHALL return `values`, `confidence`, and `rationale` inline in the synchronous response always, and SHALL include `synthesis_result_ref` as a storage-correlation pointer. Inline delivery is the normal downstream contract — not a debug-only path.
- **FR-FS-10** The service SHALL validate the generated result before reporting success. Successful output SHALL require:
  - response-schema validity,
  - a generated value present for every requested `placeholder_id`,
  - no extra keys beyond the requested `placeholder_id` set,
  - and presence of `confidence` and `rationale` in the model output.
- **FR-FS-11** The service SHALL use a managed model-access adapter consistent with ADR-0010. For the POC, the primary provider SHALL be Amazon Bedrock.
- **FR-FS-12** The service SHALL support configurable model ID, prompt-template version, and generation parameters — including temperature — without requiring a contract change.
- **FR-FS-13** Temperature is a tunable configuration setting for this service. The service SHALL default to a low but potentially non-zero temperature appropriate for natural-language generation (see §7 for rationale and recommended starting range).
- **FR-FS-14** The service SHALL support an authoritative evaluation mode in which one synthesis request maps to one model attempt and no hidden repair retry occurs, so the POC can measure actual LLM capability honestly.
- **FR-FS-15** If a developer-only repair retry mode is ever added, it SHALL be explicit, opt-in, and separately logged from authoritative evaluation runs.
- **FR-FS-16** The service SHALL record model metadata, prompt-template version, latency, token counts when available, confidence, and rationale in execution logs or stored artifacts. The immediate response to the Orchestrator NEED NOT carry all of those fields if a stable log reference is returned.
- **FR-FS-17** The service SHALL produce artifacts with explicit schema and version identifiers so stored synthesis results can be compared across prompt or model revisions.

## 6. Validation and Audit Requirements

- **FR-FS-18** The service SHALL verify that the result contains exactly the requested `placeholder_id` set — no missing values, no extra values. This is a hard gate before reporting success.
- **FR-FS-19** The service SHALL record which prompt template and model produced each synthesis artifact so prompt or model changes can be compared later against the frozen evaluation corpus from ADR-0013.
- **FR-FS-20** The service SHALL support uncached evaluation runs and SHALL default to uncached generation for POC evaluation and test-oriented development.
- **FR-FS-21** The service SHALL support a configuration switch that enables stored synthesis result reuse for production-like behavior once the team wants to exercise that path. The storage key for reuse SHALL be derived from Field Mapping's `stable_key` — specifically the `<stable_key>` component already present in the incoming `synthesis_request_ref` (which is formatted as `synthesis:<stable_key>`). Synthesis-result artifacts SHALL be keyed off that same `<stable_key>`, co-locating mapping, synthesis-request, and synthesis-result artifacts under one shared key. Deriving the key from `execution_id` would make reuse structurally impossible, since `execution_id` is unique per run.
- **FR-FS-22** The service SHALL screen free-text values in `source_payloads` within each synthesis brief for prompt-injection attempts before they are included in a Bedrock prompt (ADR-0021). Source briefs contain learner and course text and represent the primary injection surface for this service.
- **FR-FS-23** The service's Layer B capability evaluation against the frozen ADR-0013 corpus SHALL be implemented using the shared DeepEval test harness (ADR-0021). Unlike Field Mapping's deterministic comparator metric, Field Synthesis SHALL use a G-Eval metric, as it is the one service in the four-service decomposition whose primary output is genuinely open-ended natural language. The evaluation criteria SHALL include groundedness in the supplied source material, usefulness and appropriateness for the target field, and absence of fabricated claims.

## 7. Local vs AWS Requirements

- **FR-FS-24** For local development, the service SHALL support a live Bedrock-backed mode so prompt and model iteration can happen against the same provider used in AWS.
- **FR-FS-25** Local live mode SHALL rely on the normal AWS SDK credential chain rather than hard-coded credentials.
- **FR-FS-26** Local live mode SHALL require that the developer's AWS identity has the Bedrock inference permission needed for the chosen model and that the model has been enabled for the relevant account and region.
- **FR-FS-27** For local automated tests and offline development, the service SHALL support a deterministic replay or stub mode that does not require live Bedrock access.
- **FR-FS-28** Replay or stub mode SHALL preserve the same logical request and response contracts used by live mode so the Orchestrator and downstream steps do not need separate integration code paths.
- **FR-FS-29** For the AWS-shaped deployment target, the service SHALL be callable through the same logical boundary from the Orchestrator whether it is hosted as a standalone Lambda-sized service or as a dedicated handler inside a shared LLM-decision runtime.
- **FR-FS-30** For the AWS-shaped deployment target, the live service SHALL use AWS IAM-based access to Bedrock rather than application-managed third-party API keys.

## 8. Out of Scope

The Field Synthesis LLM Decision Service does not need to provide:

- deciding which fields require synthesis — that is the Field Mapping service's responsibility,
- generating JSONata expressions or synthesis placeholders,
- executing JSONata or merging synthesized values into the final payload — that is the Transformation Executor's responsibility,
- selecting delivery targets or generating workflow plans,
- direct source-system reads from LMS or skills-framework endpoints,
- synthesis for the `wallet_payload` phase under the default POC path — that phase is normally purely structural (ADR-0017: synthesis is phase-specific), so Field Mapping produces no synthesis-request artifact and this service is not invoked for it. This reflects the current plan shape, not an architectural prohibition: if a future plan marks wallet-phase fields for synthesis, the same service handles it unchanged,
- multi-turn human-in-the-loop prompt refinement,
- or automatic fine-tuning or custom model training.
