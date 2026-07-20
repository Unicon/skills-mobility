# Field Mapping LLM Decision Service Design

Status: Draft
Date: 2026-06-25
Related: [Requirements](../2_requirements/field-mapping-llm-decision-service.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [Orchestrator Design](./orchestrator.md) · [Context Builder Design](./context-builder.md) · [ADR-0005](../decisions/0005-schema-mapping-language.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Bedrock tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Overview

The **Field Mapping LLM Decision Service** is the structural mapping boundary inside the transformation pipeline. Its job is to answer one question for one transformation phase:

`How should the declared source artifacts populate this target schema?`

Per ADR-0017, the default expected transformation path for the POC has three transformation phases each corresponding to a `transformation_type`.

| `transformation_type` | Source artifacts | Target |
| --- | --- | --- |
| `credential_template` | LMS learning-context artifacts | Credential-template schema |
| `issuer_payload` | Learner-specific LMS artifacts plus the stored credential template and issuer-specific execution context | Issuer target schema |
| `wallet_payload` | Issued badge artifact plus wallet-delivery-specific execution context | Wallet target schema |

The service should be built around those three concrete source/target problems.

## 2. What the Service Produces

The service should produce two stored artifacts:

1. a **mapping artifact** containing ready-to-run JSONata for the current transformation target
2. a **synthesis-request artifact** when the mapping contains placeholder-backed fields that need Field Synthesis

The immediate service response to the Orchestrator should normally contain references to those stored artifacts, not the full JSONata program inline.

### Stored mapping artifact

Recommended shape:

```json
{
  "mapping_artifact_schema_version": "v1",
  "transformation_type": "issuer_payload",
  "source_system": "mock_lms",
  "fetch_profile_id": "skill_mastered.v1",
  "delivery_target": "learncard_issuer",
  "target_schema_ref": "schema:issuer_payload:v1",
  "jsonata": "{ ... executable JSONata target object ... }",
  "placeholder_ids": ["achievement_description"]
}
```

This artifact is intentionally compact:

- fields that map directly are represented only by executable JSONata
- fields that require synthesis are represented by placeholders inside that JSONata plus corresponding entries in the synthesis-request artifact

### Stored synthesis-request artifact

Recommended shape:

```json
{
  "synthesis_request_schema_version": "v1",
  "transformation_type": "issuer_payload",
  "requests": [
    {
      "placeholder_id": "achievement_description",
      "target_path": "achievement.description",
      "source_payload_paths": [
        "source_payloads.learner_context.course.description",
        "source_payloads.learner_context.criteria"
      ],
      "source_payloads": {
        "learner_context": {
          "course": {
            "description": "..."
          },
          "criteria": "..."
        }
      },
      "instruction": "Write a concise achievement description grounded only in the selected source content."
    }
  ]
}
```

This artifact tells Field Synthesis what each placeholder needs, without bloating the main mapping artifact. The initial design should prefer either:

- an explicit `source_input_payload` snapshot prepared by Field Mapping for that one synthesis task,
- or straightforward payload-path references into the already-supplied source payloads.

At least one of those representations must be present. If both are present, `source_payloads` should be the concrete snapshot of the values found at `source_payload_paths`.

### Placeholder format

Synthesis-backed fields use a regular JSONata path expression pointing to the synthesis output namespace:

```
synthesized.<placeholder_id>
```

`placeholder_id` is snake_case derived from the target field path (for example, `credentialSubject.achievement.description` → `achievement_description`). The Transformation Executor merges the source payloads and synthesis results into a single root data context before running JSONata:

```json
{
  "source_payloads": {
    "learner_context": { "...": "..." },
    "credential_template": { "...": "..." }
  },
  "synthesized": {
    "achievement_description": "..."
  }
}
```

Direct mappings reference `source_payloads.*` paths. Synthesis-backed fields reference `synthesized.*` paths. No sentinel values or special parsing is needed inside the JSONata itself. The `placeholder_ids` array in the mapping artifact identifies which fields are synthesis-backed so the Orchestrator and Transformation Executor know whether Field Synthesis must run before execution.

The Field Synthesis service is expected to output its results under a flat `{ "<placeholder_id>": "<text>" }` shape, which the Transformation Executor merges under the `synthesized` key before running the full JSONata program.

## 3. Runtime Shape

The recommended runtime flow is:

```text
Orchestrator
  -> Field Mapping boundary
      -> accept transient source payloads inline
      -> resolve source-resource catalogs, fetch-profile mappings, and target catalogs from service-managed lookup rules
      -> optionally resolve payload refs when inline transport is not practical
      -> optionally load configured external knowledge inputs, such as skills-framework context, when that mode is enabled
      -> build Bedrock request payload
      -> call Bedrock
      -> parse structured output
      -> validate JSONata and placeholders
      -> store artifacts
      -> return refs to Orchestrator
```

Two boundaries are important here:

- the service may resolve **stored catalogs, dictionaries, and optional payload refs**
- the service should not perform **live source-system fetches** from LMS APIs

That keeps source-of-truth fetching deterministic in the Context Builder while still letting the Field Mapping service load the artifacts and dictionaries it needs to build a good prompt.

The initial implementation should use **one Bedrock call per Field Mapping invocation**. That one call should do both logical tasks:

1. determine which target fields are `direct` vs `synthesis`
2. generate the JSONata and placeholders that implement that decision

A later experiment may split this into two Bedrock calls if quality is poor:

1. **classification call**: decide `direct` vs `synthesis` and identify the relevant source fields
2. **mapping-render call**: generate JSONata for the direct fields and placeholders plus synthesis requests for the synthesis fields

The default design should remain one call until testing shows a concrete reason to split it.

## 4. Request Contract

The request should be transient-payload-first:

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "transformation_type": "issuer_payload",
  "source_system": "mock_lms",
  "fetch_profile_id": "skill_mastered.v1",
  "delivery_target": "learncard_issuer",
  "synthesis_allowed": true,
  "source_payloads": {
    "learner_context": { "...": "transient payload" },
    "credential_template": { "...": "transient payload" },
    "profile_resolution": { "...": "transient payload" }
  }
}
```

`transformation_type` and `delivery_target` are independent inputs, not a derived pair. Both are supplied by the Workflow Actions delivery-phase plan as step-level literals (see [Orchestrator Design](./orchestrator.md) §5, Example Phase 1 plan), because that plan is the one place that already knows both which transformation phase a step performs and which delivery target it serves. The Field Mapping service does not derive either field from the other, and the Orchestrator does not maintain a separate mapping table between them.

`synthesis_allowed` is a third literal supplied by the same Workflow Actions delivery-phase plan. It is a permission gate, not a prediction: it authorizes whether Field Synthesis may be used for this phase at all, because the Orchestrator has no mechanism to route a synthesis request for a phase whose plan didn't provision one. See §6 for the resulting classification rule.

The main design choice is that the Orchestrator passes transient source payloads inline by default. That keeps the working data ephemeral inside the execution unless there is a practical reason to materialize it elsewhere.

If a payload is already stored or is too large to pass inline comfortably, the contract may allow an optional payload reference instead. That is a fallback, not the default.

`delivery_target` applies only to `issuer_payload` and `wallet_payload` requests. `credential_template` requests omit it entirely: it is not present as `null` or an empty string, it is simply absent from the request. This follows [ADR-0017](../decisions/0017-three-transformation-phases.md), which establishes that the `credential_template` phase has no `delivery_target`. For example, a `credential_template` request looks like the `issuer_payload` example above with `delivery_target` removed:

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "transformation_type": "credential_template",
  "source_system": "mock_lms",
  "fetch_profile_id": "skill_mastered.v1",
  "synthesis_allowed": true,
  "source_payloads": {
    "learner_context": { "...": "transient payload" }
  }
}
```

The Orchestrator should not have to know the catalog or data-dictionary reference IDs. Instead, the Field Mapping service should resolve the correct source-resource catalogs, fetch-profile mappings, and target catalogs from:

- `source_system`
- `fetch_profile_id`
- `delivery_target`
- `transformation_type`

For `credential_template` requests, resolution uses only `source_system`, `fetch_profile_id`, and `transformation_type`; `delivery_target` is omitted for that phase.

Prompt templates, model IDs, temperatures, and any configured knowledge sources should be runtime configuration of the Field Mapping service, not core business inputs on every request.

## 5. Source and Target Catalog Store

Part of building this service is building the POC's **source and target schema catalog / data-dictionary store**. The service depends on those definitions to explain the mapping problem clearly to the model. **Building the catalog files is an explicit development deliverable for this service** — these files do not pre-exist and must be authored during implementation.

Recommended POC approach:

- keep the canonical catalog definitions in version-controlled files in the repo
- populate those definitions from source-system and target-system documentation when available
- seed those definitions into the local and AWS storage layers used by the POC
- resolve them at runtime through stable identifiers rather than hard-coded Python constants spread across the service

### Source-resource catalog provenance

Source-resource catalog files (one per resource endpoint) should be built from the **Mock LMS Canvas-style endpoint schemas**. The Mock LMS models Canvas LMS resources (outcomes, assignments, modules, users, submissions, etc.). The Canvas LMS Resource API documentation is the reference for field shapes and descriptions.

The fetch-profile mapping files in `catalogs/fetch_profiles/mock_lms/` should be derived from the **Context Builder fetch profiles** defined in the Context Builder design (see [Context Builder Design](./context-builder.md) Section 5). Each fetch profile (for example, `skill_mastered.v1`) declares which resource endpoints it fetches — that list becomes the set of source-resource catalog identifiers in the corresponding fetch-profile mapping file. The `skill_mastered.v1` profile fetches: outcome, assignment, rubric (conditional), module_context, module_pages, canvas_user, and submission.

### Target catalog provenance

The primary `issuer_payload` target catalog for `learncard_issuer` should be built from the **LearnCard SDK `UnsignedVC` object schema**. The `UnsignedVC` shape defines the required and optional fields for unsigned Open Badges v3 / BoostCredential payloads, including `credentialSubject.achievement`, `credentialSubject.id`, `issuer`, `issuanceDate`, `name`, `image`, and `display`.

The `credential_template` target catalog has no `delivery_target` subdirectory, since this phase has no `delivery_target` ([ADR-0017](../decisions/0017-three-transformation-phases.md)). Its target schema should mirror the output of the [DCC Credential Co-writer](https://co-writer.dcconsortium.org/), the Digital Credentials Consortium's tool for generating Open Badges 3.0 / W3C Verifiable Credentials, which the `credential_template` phase is explicitly modeled after. The tool's exact field-level output schema is not available from published documentation, so it is not reproduced here. Capturing that schema, by exercising the live tool with representative sample input, is an explicit development deliverable for this service (see FR-FM-5a), the same way the other catalog files are.

The `wallet_payload` target catalog covers both real wallet delivery targets. The `learncard_wallet` catalog should be built from the LearnCloud Network API's `POST /credential/send/{profileId}` endpoint and the LearnCard SDK's `sendCredential` / `send` methods, already documented in [LearnCard Wallet Adapter Requirements](../2_requirements/learncard-wallet-adapter.md). The `smart_resume` catalog should be built from SmartResume's CredentialConnect API (https://my.smartresume.com/api/v1/docs), which accepts Open Badges 3.0 or Comprehensive Learner Record 2.0 JSON-LD credentials directly via endpoints such as `/api/v1/credentials` and `/api/v1/clr`. Because [Phase 1](../2_requirements/phase-1-poc-slice.md) excludes SmartResume delivery and prioritizes LearnCard-only delivery, the `smart_resume` catalog may be authored after the `learncard_wallet` catalog rather than in the same increment.

On the source side, the design should distinguish between:

- **source-resource catalogs**, which describe the fields for one source endpoint or resource schema
- **fetch-profile mappings**, which relate `source_system + fetch_profile_id` to the one or more source-resource endpoint schema catalogs used by that deterministic fetch profile

In the current POC, `fetch_profile_id` should be treated as the identifier for the deterministic Context Builder fetch profile, which will usually align closely with one event type. It should not be embedded into each source-field definition because one fetch profile can expand to multiple endpoint or resource schemas.

Recommended source-resource catalog contents:

- `source_system`
- resource or endpoint schema identifier
- field path
- field description
- data type
- whether the field is required
- whether the field is an array
- example value

Recommended fetch-profile mapping contents:

- `source_system`
- `fetch_profile_id`
- list of source resource or endpoint schema identifiers included in the profile
- any stable payload aliases used for those resources in the `source_payloads` envelope

Recommended target-catalog contents:

- `delivery_target`
- `transformation_type`
- target field path
- field description
- data type
- whether the field is required
- whether the field is an array
- example value
- no-mapping behavior rule when no credible mapping exists, such as `omit`, `null`, `blank`, or disallowed

For the POC, a pragmatic implementation is:

- prefer OpenAPI 3.1 JSON or YAML files for source-resource catalogs and target catalogs when practical
- use standard OpenAPI and JSON Schema fields for description, data type, required fields, arrays, and examples
- use vendor extensions only for POC-specific metadata such as `x-source-system`, `x-resource-schema-id`, `x-transformation-type`, or `x-no-mapping-behavior`
- keep a separate committed mapping file or table for `source_system + fetch_profile_id`
- a simple loader that seeds local SQLite and the AWS-side equivalent store
- lookup tables keyed by `source_system + resource_schema_id`, `source_system + fetch_profile_id`, and `delivery_target + transformation_type`

The important constraint is that catalog edits are reviewable and versioned. The store should not begin as a manually curated runtime-only database with no committed source of truth.

## 6. How Classification Works

The service conceptually still performs two logical steps:

1. decide whether each target field is `direct` or `synthesis`
2. express that decision as JSONata plus placeholders

But that classification does not need to be carried around as a bulky separate runtime payload. It can be implicit:

- if a target field is represented by normal JSONata, it is `direct`
- if a target field is represented by a placeholder and an entry exists in the synthesis-request artifact, it is `synthesis`

This design keeps the downstream artifact compact while still leaving enough evidence for testing and debugging. If the team wants explicit per-field classification metadata for evaluation, that can be logged or stored as a secondary artifact without burdening the normal orchestration contract.

### Honoring `synthesis_allowed`

The request's `synthesis_allowed` field constrains this classification asymmetrically, not symmetrically:

- If `synthesis_allowed` is `false`, the service must not classify any field as `synthesis`. Every target field must resolve to `direct` JSONata, falling back to the target catalog's no-mapping behavior rule (`omit`/`null`/`blank`/disallowed) for anything that cannot be mapped directly. This is a hard constraint, not a preference the service can weigh against its own analysis: the Orchestrator has no mechanism to route a synthesis request for a phase whose plan didn't provision a Field Synthesis step, so a `false` value is binding.
- If `synthesis_allowed` is `true`, the service is not obligated to use synthesis. If its own analysis finds no field genuinely needs it, it may still classify every field as `direct` and report `requires_synthesis: false`. A `true` value permits synthesis; it does not require it.

For the POC, the Workflow Actions delivery-phase plan is expected to pass `synthesis_allowed: false` for wallet-payload requests, because the current plan shape (see [Orchestrator Design](./orchestrator.md) §5) has no Field Synthesis step for the wallet phase. That omission is a property of the plan Workflow Actions produces for this phase, not a rule hardcoded into the Field Mapping service or the Orchestrator's execution engine — the Orchestrator executes whatever steps a plan contains and would run a wallet-phase Field Synthesis step if a future plan included one.

## 7. LLM Invocation and Prompting Strategy

The initial implementation should make **one Bedrock Converse request** for each Field Mapping invocation.

That one request should contain:

- one **system prompt** template file that defines the service role and hard rules
- one **request message** assembled from the current transformation inputs
- one **structured-output schema** that constrains the model's response

The Bedrock request is therefore one inference payload, not multiple unrelated prompt files or multiple unrelated model calls.

Bedrock's Converse API uses role labels such as `system`, `user`, and `assistant`. In this design, the Bedrock `user` role message is an application-built request message in a server-to-server pipeline, not a human chat message.

### Bedrock request inputs

The request message should include, in structured or clearly delimited form:

- `transformation_type`
- `source_system`
- `fetch_profile_id`
- `delivery_target`
- the source payloads relevant to the current transformation
- the resolved source-field catalog excerpt relevant to those payloads
- the resolved target-field catalog excerpt for the target schema, including its no-mapping behavior rules

### Bedrock response output

The model response should be constrained to a schema that includes at minimum:

- the generated JSONata mapping artifact body
- any synthesis-request entries needed for placeholders
- `confidence`
- `rationale`

#### Confidence and rationale format

`confidence` is a single overall float in [0.0, 1.0] representing the model's confidence that the mapping is correct and complete across all fields. It is not a per-field score.

`rationale` is 1–3 sentences summarizing the overall mapping decision, **plus a one-line note for each field that was not a straightforward direct mapping** — every synthesis field and every omit/null/blank field gets a brief reason (e.g. `"achievement.description → synthesis: requires narrative composition from course description and learning outcomes"`). Direct fields need no individual note because their mapping is self-evident from the JSONata. For a target schema with many fields this keeps the rationale readable without becoming exhaustive (typically < 200 words for a ~100-field target).

### Prompt content

The system prompt and request message together should tell the model all of the following:

- it is mapping the supplied source payloads to the supplied target schema
- it should work through target schema fields **one by one**: for each, consult the target catalog entry (description + `x-no-mapping-behavior`) and the relevant source-field catalog(s) + source payloads, decide direct / synthesis / omit, and emit the corresponding JSONata or placeholder before moving to the next field
- direct mappings must reference only source fields that actually exist in the supplied payloads
- synthesis requests must identify the relevant source material for the synthesis task
- final human-facing synthesis text must not be generated in this service
- the output must be valid, machine-executable JSONata plus the required structured metadata

### Prompt tuning emphasis

Prompt tuning for this service will likely focus heavily on the boundary between `direct` and `synthesis`. That is one of the key evaluation questions for the POC.

Expected tuning levers include:

- clarifying what counts as a straightforward direct map
- clarifying when summarization, interpretation, or narrative composition requires synthesis instead
- adding representative examples of `direct` vs `synthesis` decisions

Prompt tuning should operate on prompt wording, examples, and catalog quality. It should not silently rewrite source payload contents or replace documented field meanings with ad hoc interpretations.

Prompt templates should live in version-controlled files so prompt changes can be reviewed and compared against the evaluation corpus.

## 8. Optional External Knowledge Inputs

In this document, **optional external knowledge inputs** means additional reference material that is not already present in the source payloads or the source/target catalogs. The most likely example is external skills-framework context, but the same category could also include standards documentation or other curated reference material.

Bedrock models do not browse the web on their own. If the service uses optional external knowledge inputs, the application must supply them explicitly.

For the **first round of POC testing**, the Field Mapping service should use **no optional external knowledge inputs**. It should rely only on:

- the supplied source payloads
- the supplied source and target catalogs
- the model's existing priors

Optional external knowledge inputs should be treated as a later lever the team can pull if:

- the model does not perform well enough without it,
- or the model performs acceptably but the team wants to test whether explicit grounding improves output quality further.

If optional external knowledge inputs are introduced later, the recommended options are:

1. curated skills-framework snapshots stored by the application
2. a service-managed retrieval step against configured documents or websites before prompt assembly

The important design constraint is that this behavior must be explicit and reproducible. It should never depend on an implicit assumption that the Bedrock model is browsing the internet.

## 9. Bedrock Invocation Design

### Primary platform

Amazon Bedrock is the POC's primary managed inference platform per ADR-0010. Per ADR-0010, the Field Mapping service should interact with model providers through a **thin provider adapter** rather than embedding Bedrock-specific request construction throughout the service logic. This can allow for the ability to easily switch to a different model provider in the future if desired.

For the POC, the concrete adapter implementation should target Bedrock's **Converse API**, which is Bedrock's message-based interface for sending a system prompt plus one or more role-labeled messages to a model and receiving the model's response in a standardized request/response shape.

For this service, the Bedrock interaction sequence is:

1. screen free-text values in `source_payloads` for prompt-injection attempts (ADR-0021) before they reach the prompt
2. build the prompt and structured-output schema
3. call the provider adapter, which invokes Bedrock `Converse` through the AWS SDK
4. parse the returned structured object
5. validate it against the supplied payload fields and resolved target schema
6. store the artifacts

The concrete SDK surface should follow the currently documented Bedrock `Converse` and structured-output APIs at implementation time. The important design point is not one exact SDK call signature; it is that the service uses:

- a thin provider adapter boundary consistent with ADR-0010
- Bedrock's messages-style inference interface
- a schema-constrained structured response
- low-temperature generation suitable for machine-executable output

Bedrock structured outputs can enforce JSON-schema-conformant results for Converse requests, and AWS documents that first-time schema compilation can add latency before the compiled grammar is reused for later calls. That behavior should be expected during development and testing. Sources: [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) and [Boto3 `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).

### Recommended starting settings

- `temperature`: `0.0`
- `max_tokens`: high enough to return the full mapping artifact for the largest expected phase input
- one baseline Bedrock model across services initially, then per-service tuning later

### Access pattern

- local live mode: use the normal AWS SDK credential chain
- AWS deployment: use IAM roles for Lambda or the hosting runtime

That is the Bedrock best practice. No separate API-key layer should be introduced for a Bedrock-backed service.

## 10. Response Contract

The synchronous response shape:

```json
{
  "status": "succeeded",
  "mapping_artifact_ref": "mapping:123",
  "synthesis_request_ref": "synthesis:456",
  "requires_synthesis": true,
  "llm_invocation_log_ref": "llmcall:789",
  "synthesis_request": { "...": "inline synthesis-request artifact" }
}
```

`synthesis_request` carries the synthesis-request artifact inline when `requires_synthesis` is `true`; it is `null` otherwise. This inline handoff is the established design: the Field Mapping and Field Synthesis services maintain separate artifact stores, so a bare `synthesis_request_ref` does not resolve across that boundary. The Orchestrator passes the inline artifact directly to the Field Synthesis service without a cross-store lookup.

This keeps the Orchestrator contract stable and lightweight for all other fields. The Orchestrator should not need all model metadata inline if it can retrieve that detail through the logged reference.

`requires_synthesis` is a derived convenience field, not an independent source of truth: `requires_synthesis == synthesis_allowed && (placeholder_ids non-empty) && (synthesis_request_ref != null)`. Including `synthesis_allowed` in the derivation makes the §6 constraint self-enforcing at the field level: `requires_synthesis` can never be `true` when the request forbade synthesis, regardless of what `placeholder_ids` or `synthesis_request_ref` happen to contain.

The Orchestrator passes `mapping_artifact_ref` through opaquely as the step's output binding; it does not resolve the reference into the underlying JSONata itself. The **Transformation Executor** is the component responsible for dereferencing `mapping_artifact_ref` (and the corresponding synthesized values once Field Synthesis has resolved `synthesis_request_ref`) against the artifact store before it runs the JSONata against the source payloads.

## 11. Validation

The service should validate before reporting success:

1. parse the structured model response
2. verify that the artifact shape matches the requested `transformation_type`
3. verify that placeholder-backed fields have corresponding synthesis requests
4. parse-check the JSONata against the same dialect assumptions the Transformation Executor will use, once a Transformation Executor design confirms what those assumptions are (no Transformation Executor design exists yet in this repo, so today this is a stated intent, not a verified fact)
5. verify that the generated JSONata references only fields available in the supplied source payloads
6. verify that the generated output shape is valid for the resolved target schema
7. store only validated artifacts as successful results

This service should not silently fall back to handwritten Python mappings if the model output is bad. That would defeat the POC's purpose.

Invalid outputs should still be stored as **failed artifacts** or failed invocation records, with their validation errors attached. They should not be reusable as successful mapping artifacts, but they are valuable evidence for prompt tuning, model comparison, and post-run analysis.

### Capability Evaluation (Layer B)

The checks above are hard gates (ADR-0013 Layer A), not a capability verdict. Field Mapping's Layer B capability evaluation, meaning executed-result correctness plus semantic alignment to a human-authored canonical mapping, is implemented as a deterministic custom metric in the shared DeepEval harness (ADR-0021), scored against the frozen evaluation corpus. This is plain code, not an LLM-as-judge metric: no judge-model cost applies, unlike Field Synthesis's `G-Eval` metric.

## 12. Repair Retry Mode

A **repair retry** or **repair loop** means:

- the model returns an invalid mapping artifact
- the service feeds the validation error back to the model
- the model gets another chance to regenerate a corrected version

That can be useful for experimentation, but it must not be hidden in the authoritative evaluation path. Otherwise the POC stops measuring "can the model do the job in one real attempt?" and starts measuring "can we rescue a bad attempt with extra scaffolding?"

Recommended rule:

- authoritative evaluation mode: exactly one model attempt
- optional developer repair mode: explicit, off by default, separately logged

If the team later explores repair retries, the service should log at minimum:

- whether a retry was used
- how many retries were used
- the validation error that triggered each retry
- whether the final successful artifact required repair

The POC does not need to define an acceptable retry rate yet. The important first step is to measure it explicitly if the feature is turned on.

## 13. Stored Artifact Reuse

For this POC, the default should be **fresh generation without reusing stored mapping artifacts** so the team can observe whether the model can actually do the mapping job.

The service should still support **stored artifact reuse** by configuration because that is the more realistic production-like behavior. But reuse should be opt-in, not the default evaluation path.

Recommended behavior:

- default local/test setting: `reuse_stored_mapping_artifacts = false`
- production-like or performance-testing setting: `reuse_stored_mapping_artifacts = true`

## 14. Observability and Evaluation Data

The service should store enough data for the team to evaluate output quality, cost, and tuning opportunities over time.

At minimum, each invocation record or stored artifact linkage should make it possible to recover:

- `execution_id`
- `transformation_type`
- `source_system`
- `fetch_profile_id`
- `delivery_target`
- prompt-template version
- model ID
- provider
- generation settings such as temperature
- input token count when available
- output token count when available
- latency
- the raw structured model output itself or a stable reference to where that output is stored
- model-reported `confidence`
- model-reported `rationale`
- validation outcome
- whether repair retry mode was enabled and whether it was used
- `corpus_scenario_id`, present only for invocations run against the frozen ADR-0013 evaluation corpus (absent for live production invocations), formatted as `{event_type}.{scenario_slug}.v{version}` per [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) §8

This data is necessary not just for debugging individual failures, but for comparing:

- prompt versions
- model choices
- direct-vs-synthesis behavior
- retry behavior
- cost and latency tradeoffs

## 15. Suggested Module Layout

The implementation can stay small:

```text
field_mapping/
  contracts.py
  prompt_templates/
    field_mapping.v1.md
  catalogs/
    sources/
      mock_lms/
        <resource-endpoint-1>.openapi.json
        <resource-endpoint-2>.openapi.json
    targets/
      credential_template/
        credential_template.openapi.json
      learncard_issuer/
        issuer_payload.openapi.json
      learncard_wallet/
        wallet_payload.openapi.json
      smart_resume/
        wallet_payload.openapi.json
    fetch_profiles/
      mock_lms/
        <fetch_profile_id>.json
  catalog_store.py
  artifact_loader.py
  prompt_builder.py
  llm_adapter.py
  bedrock_adapter.py
  replay_adapter.py
  validators.py
  artifact_store.py
  service.py
  api.py
```

Responsibilities:

- `contracts.py`: request/response schemas
- `catalogs/`: committed OpenAPI source and target schema files plus committed fetch-profile mapping files; for the POC this should include one source schema file per Mock LMS resource endpoint and one target schema file for each of the `credential_template`, LearnCard issuer, LearnCard wallet, and SmartResume wallet target catalogs
- `catalog_store.py`: resolve source-resource catalogs, target catalogs, and fetch-profile mappings
- `artifact_loader.py`: resolve source payloads and optional payload refs
- `prompt_builder.py`: render system prompts and request messages from the loaded inputs
- `llm_adapter.py`: define the provider-adapter protocol and shared result shape
- `bedrock_adapter.py`: implement the provider adapter using Bedrock `Converse` plus invocation-log capture
- `replay_adapter.py`: implement deterministic local replay without live Bedrock access
- `validators.py`: artifact-shape and JSONata validation
- `artifact_store.py`: persist mapping and synthesis-request artifacts
- `service.py`: orchestration of load -> prompt -> model -> validation -> store -> response
- `api.py`: FastAPI and Lambda entrypoint boundary

## 16. Build Order

Recommended implementation order:

1. Define the transient-payload-first request contract and the ref-returning response contract.
2. Define the stored mapping-artifact and synthesis-request-artifact schemas.
3. Build the committed source-resource catalogs, target catalogs, and fetch-profile mappings.
4. Implement artifact and catalog loading.
5. Implement JSONata and placeholder validation.
6. Add a deterministic replay adapter and fixture-driven tests.
7. Add the provider-adapter boundary, the Bedrock implementation, and the prompt templates.
8. Wire the Orchestrator seam to the new response contract.
9. Enable live Bedrock mode for prompt and model iteration.

That order keeps the service measurable and honest from the start.

## 17. Implementation Decisions

Decisions made during pre-development design review that are not already captured in ADRs.

### JSONata library

**`jsonata-python`** is the selected Python JSONata library. It is actively maintained, pure Python, supports Python ≥ 3.10, and provides `get_errors()` for parse validation without execution — which is the hard gate needed at validation step 4 in Section 11. This is consistent with the broader project's Python-first stack and avoids introducing a Node.js subprocess for JSONata parsing.

### Starting model

**Claude Haiku 4.5** is the starting model. The exact invocable Bedrock model ID string (which may include a date and version suffix, per AWS's typical Bedrock ID format) should be verified against the current AWS Bedrock model catalog at implementation time rather than hardcoded from this doc, since model ID formats change. This is accessed via the Bedrock Converse API. Per the recommended settings in Section 9, temperature should be `0.0` for this service's structured mapping task. The model ID should be runtime configuration so it can be changed without a code change.

### Artifact storage for local development

**File-based JSON storage** is the local development artifact storage approach. Mapping artifacts and synthesis-request artifacts are written to and read from local JSON files keyed by a stable identifier (for example, derived from `source_system`, `fetch_profile_id`, `transformation_type`, and `delivery_target`). This avoids any running infrastructure dependency during local development and testing while preserving the same logical `artifact_store.py` interface that will be backed by a cloud storage layer in AWS.
