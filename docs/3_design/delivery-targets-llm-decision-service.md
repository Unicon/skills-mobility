# Delivery Targets LLM Decision Service Design

Status: Draft
Date: 2026-07-10
Related: [Requirements](../2_requirements/delivery-targets-llm-decision-service.md) · [Field Mapping Design](./field-mapping-llm-decision-service.md) · [Workflow Actions Design](./workflow-actions-llm-decision-service.md) · [Orchestrator Design](./orchestrator.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0014](../decisions/0014-poc-storage-strategy.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Overview

The **Delivery Targets LLM Decision Service** is the routing boundary inside the orchestration pipeline. Its job is to answer one question for one workflow execution:

`Which downstream systems should receive transformed data for this event?`

Per [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md), this is "primarily a routing and eligibility decision. It reasons over event type, learner state, and available targets to produce a small set of destinations. The prompt is relatively stable and the output schema is simple." That makes this service structurally simpler than the Field Mapping service: there is one decision, one small structured output, and no artifact generation (no JSONata, no placeholders, no synthesis requests).

A **Policy Rules Service** (for deterministic policy enforcement against institutional eligibility rules) is out of scope for the POC. For this service, eligibility reasoning is carried entirely by the human-readable descriptions in the available-delivery-targets catalog (§5) and by LLM judgment against those descriptions.

The available delivery targets for the POC come from [ADR-0016](../decisions/0016-delivery-routing-topology.md):

| Delivery target | Delivery action | Adapter | Runtime |
| --- | --- | --- | --- |
| `learncard_issuer` | `issue_learncard_badge` | LearnCard Issuer Adapter | Node/TypeScript |
| `learncard_wallet` | `deliver_to_learncard_wallet` | LearnCard Wallet Adapter | Python |
| `smart_resume` | `deliver_to_smartresume` | SmartResume Wallet Adapter | Python |

The service selects a subset of those three. It does not decide *how* to deliver, and it does not perform delivery — that is the Delivery Router and adapters (ADR-0016).

### Where it sits in the workflow

The Orchestrator runs this service at the `select_delivery_targets` seam, after the pre-target Workflow Actions gate decides the workflow should continue, and before the delivery-phase Workflow Actions plan (see [Orchestrator Design](./orchestrator.md) §3):

```text
... Workflow Actions pre-target gate
    -> Delivery Targets            <-- this service
    -> Workflow Actions delivery-phase plan (receives selected targets)
    -> ... Field Mapping / execution / delivery ...
```

Two sequencing facts anchor this design:

- **Delivery Targets must resolve before Transformation Mappings** — a hard dependency in ADR-0007, because the mapping instructions depend on which targets were selected.
- **The delivery-phase plan consumes the selected targets** — the second Workflow Actions call receives `selected_targets` as an input and builds the delivery-phase plan around them ([Orchestrator Design](./orchestrator.md) §4 `applicability.selected_targets`).

## 2. What the Service Produces

The service produces one stored artifact: a **selection artifact** naming the selected targets, each with a confidence score and a rationale. Unlike Field Mapping, it produces no executable artifact and no secondary synthesis-request artifact.

The service returns the full selection output — selected targets, per-target confidence, and rationale — inline in the synchronous response. The service also stores the selection artifact; a `selection_artifact_ref` may be included in the response for storage correlation. The Orchestrator does not need a second round-trip to retrieve the selection.

### Stored selection artifact

Recommended shape:

```json
{
  "selection_artifact_schema_version": "v1",
  "event_type": "skill_mastered",
  "source_system": "mock_lms",
  "selected_targets": [
    {
      "delivery_target": "learncard_issuer",
      "confidence": 0.98,
      "rationale": "Skill-mastered events produce a verifiable achievement that should be issued as an Open Badge."
    },
    {
      "delivery_target": "learncard_wallet",
      "confidence": 0.95,
      "rationale": "The learner has a resolvable LearnCard wallet profile, so the issued badge should be delivered to it."
    }
  ]
}
```

The `selected_targets` values are drawn only from the available-delivery-targets catalog (§5). `confidence` is the model's 0–1 self-assessment and `rationale` is a brief natural-language explanation, consistent with the confidence/rationale structured-output contract in [ADR-0010](../decisions/0010-llm-model-access-strategy.md) §165.

## 3. Response Contract

The synchronous response returns the selection inline:

```json
{
  "status": "succeeded",
  "selected_targets": [
    {
      "delivery_target": "learncard_issuer",
      "confidence": 0.98,
      "rationale": "Accounting course (ACCY-*); routes to LearnCard via the Pretend Association of Accountants partnership."
    },
    {
      "delivery_target": "learncard_wallet",
      "confidence": 0.95,
      "rationale": "Paired with learncard_issuer to deliver the issued badge to the learner's wallet."
    }
  ],
  "selection_artifact_ref": "selection:123",
  "llm_invocation_log_ref": "llmcall:789"
}
```

The inline `selected_targets` is the primary contract: the Orchestrator can read the selected targets, confidence, and rationale directly without a second round-trip. The `selection_artifact_ref` is optional — it is included for storage correlation so auditors can navigate to the stored artifact. `llm_invocation_log_ref` points to the technical invocation record (model ID, prompt-template version, token counts, latency, raw model output) for prompt engineers and operators.

Both refs are returned even for failed invocations; the records are retained as evidence for prompt tuning.

## 4. Runtime Shape

The recommended runtime flow is:

```text
Orchestrator
  -> Delivery Targets boundary
      -> accept event_type, source_system, learner context inline
      -> resolve the available-delivery-targets catalog from service-managed configuration
      -> screen free-text context values for prompt injection (ADR-0021)
      -> build Bedrock request payload
      -> call Bedrock (one Converse request)
      -> parse structured output
      -> validate selection against the available/eligible target set (hard gate)
      -> store selection artifact + invocation log
      -> return inline selected_targets (with confidence + rationale) + optional refs to Orchestrator
```

The initial implementation should use **one Bedrock call per Delivery Targets invocation**. This is a single, simple decision; there is no reason to split it. If routing quality is poor, prompt tuning and catalog quality are the first levers (§7), not additional calls.

The service resolves the **available-delivery-targets catalog** but does not perform live source-system fetches — the decision context is assembled deterministically by the Context Builder and passed in the request. That keeps source-of-truth fetching in the Context Builder while letting this service load the target catalog it needs to explain the routing options to the model.

## 5. Available Delivery Targets Catalog

Part of building this service is authoring the POC's **available-delivery-targets catalog**. The service depends on this definition to explain the routing options clearly to the model. **Building the catalog file is an explicit development deliverable for this service** — it does not pre-exist and must be authored during implementation, the same treatment FR-FM-5a gives Field Mapping's catalogs.

Recommended POC approach:

- keep the canonical catalog definition in a version-controlled file in the repo,
- populate it from [ADR-0016](../decisions/0016-delivery-routing-topology.md)'s enumerated targets and their delivery actions,
- seed it into the local and AWS storage layers used by the POC,
- resolve it at runtime through a stable identifier rather than hard-coded Python constants spread across the service.

Recommended catalog contents, per target:

- `target_id` — the delivery-target identifier (`learncard_issuer`, `learncard_wallet`, `smart_resume`), matching the `DeliveryTarget` ids in §1
- `description` — a human-readable description written in the voice of an institution administrator filling out a configuration form, not a polished doc-site summary (see FR-DT-5a)

The admin-voice framing matters for evaluation: the LLM's routing performance is being assessed against natural admin-authored descriptions. Over-editing catalog entries for literary quality would skew that evaluation. Write descriptions as a realistic admin would; don't clean them up.

**Catalog schema:** each entry is an object with a `target_id` (matching the `DeliveryTarget` ids in §1) and an administrator-authored `description` (the routing rationale, written in the institution-admin voice). Example:

```json
[
  {
    "target_id": "learncard_issuer",
    "description": "LearnCard badge issuer — our only issuer, so every credential we send out runs through here first, regardless of course subject. Only the final delivery step varies by subject."
  },
  {
    "target_id": "learncard_wallet",
    "description": "LearnCard learner wallet — used alongside learncard_issuer for Accounting courses (ACCY-*). The Pretend Association of Accountants partners with LearnCard, so these badges reach their employer members in the learner's wallet."
  },
  {
    "target_id": "smart_resume",
    "description": "SmartResume — the final delivery step for Finance courses (FINC-*), after issuance through learncard_issuer. The Pretend Association of Finance partners with SmartResume for credential delivery to their members."
  }
]
```

> Open question: ADR-0016 defines the delivery-action-to-adapter topology but does not define per-target *eligibility attributes*. For the POC, eligibility is expressed through the catalog's human-readable descriptions and resolved by LLM judgment; the deterministic hard gate (§9) is limited to catalog membership. Deterministic policy enforcement against richer eligibility rules (a future Policy Rules Service) is out of scope for the POC.

The routing bifurcation for evaluation follows the institution's configured partnership associations: credentials from Accounting (`ACCY-*`) courses route to `learncard_issuer` + `learncard_wallet` (via the Pretend Association of Accountants / LearnCard partnership); credentials from Finance (`FINC-*`) courses route to `smart_resume` (via the Pretend Association of Finance / SmartResume partnership). Catalog entries for each target should be authored in the admin voice describing these partnership associations. No sample-data change is required — the existing ACCY/FINC subjects provide the bifurcation. In every case the LearnCard issuer (`issue_learncard_badge`) runs first — it is the only issuer this POC supports — so the selected target distinguishes only the final delivery step (`learncard_wallet` vs `smart_resume`), not the whole pipeline.

The important constraint, as with the Field Mapping catalogs, is that catalog edits are reviewable and versioned. The store should not begin as a manually curated runtime-only database with no committed source of truth.

For POC storage, this catalog corresponds to the **Delivery Targets Store** logical store identified in [ADR-0014](../decisions/0014-poc-storage-strategy.md). Local development can back it with file-based JSON (see §13); the AWS-shaped target mirrors ADR-0014's storage direction.

## 6. Request Contract

The request should be transient-context-first:

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "event_type": "skill_mastered",
  "source_system": "mock_lms",
  "learner_context": { "...": "transient context bundle subset" }
}
```

Per [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md), the key inputs are event type, learner context, and the available delivery targets. The available targets are **not** in the request — the service resolves them from its own catalog (§5), so the Orchestrator does not have to enumerate targets or know catalog identifiers.

A `policy_context` field is not included in the POC request contract — a Policy Rules Service is out of scope for the POC (see §1). If policy context is introduced in a future phase, it can be added as an additional request field without changing the core contract.

The Orchestrator passes the learner context inline by default, consistent with how it treats the Context Builder bundle as opaque JSON ([Orchestrator Design](./orchestrator.md) §4). If a context payload is already stored or is too large to pass inline comfortably, the contract may allow an optional reference instead. That is a fallback, not the default.

Prompt templates, model IDs, temperatures, and generation parameters are runtime configuration of the service, not core business inputs on every request.

## 7. LLM Invocation and Prompting Strategy

The initial implementation should make **one Bedrock Converse request** for each Delivery Targets invocation.

That one request should contain:

- one **system prompt** template file that defines the service role and hard rules,
- one **request message** assembled from the current event and learner context,
- one **structured-output schema** that constrains the model's response.

Bedrock's Converse API uses role labels such as `system`, `user`, and `assistant`. Here the Bedrock `user` role message is an application-built request message in a server-to-server pipeline, not a human chat message.

### Bedrock request inputs

The request message should include, in structured or clearly delimited form:

- `event_type`
- `source_system`
- the learner context relevant to routing eligibility
- the resolved available-delivery-targets catalog (target ids and administrator-authored descriptions)

### Bedrock response output

The model response should be constrained to a schema that includes at minimum:

- `selected_targets`: an array whose entries each carry `delivery_target`, `confidence`, and `rationale`

The output schema is deliberately small and stable, per ADR-0007 ("the output schema is simple"). The set of valid `delivery_target` values is closed to the catalog.

### Prompt content

The system prompt and request message together should tell the model all of the following:

- it is selecting which downstream targets should receive transformed data for this event,
- it may select only from the supplied available-delivery-targets catalog,
- it should weigh event type and learner context against each target's administrator-authored description,
- it must assign each selected target a confidence and a rationale,
- it must not invent targets or delivery mechanics, and must not decide transformation or workflow steps.

### Prompt tuning emphasis

Prompt tuning for this service will likely focus on the **routing boundary**: when an event/learner combination warrants a given target versus not. Expected tuning levers include clarifying each target's administrator-authored description in the catalog, adding representative examples of correct routing decisions, and calibrating how confidently the model should select a target given partial context. Prompt templates should live in version-controlled files so changes can be reviewed and compared against the evaluation corpus.

## 8. Bedrock Invocation Design

### Primary platform

Amazon Bedrock is the POC's primary managed inference platform per [ADR-0010](../decisions/0010-llm-model-access-strategy.md). The service should interact with model providers through a **thin provider adapter** rather than embedding Bedrock-specific request construction throughout the service logic, so a different provider could be substituted later without changing service logic.

For the POC, the concrete adapter implementation should target Bedrock's **Converse API**. The Bedrock interaction sequence for this service is:

1. screen free-text values in the learner context for prompt-injection attempts ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)) before they reach the prompt
2. build the prompt and structured-output schema
3. call the provider adapter, which invokes Bedrock `Converse` through the AWS SDK
4. parse the returned structured object
5. validate it against the available/eligible target set (§9)
6. store the artifact and invocation log

The important design point is not one exact SDK call signature; it is that the service uses a thin provider adapter boundary consistent with ADR-0010, Bedrock's messages-style inference interface, a schema-constrained structured response, and low-temperature generation suitable for a stable routing decision.

Bedrock structured outputs can enforce JSON-schema-conformant results for Converse requests; AWS documents that first-time schema compilation can add latency before the compiled grammar is reused. Sources: [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) and [Boto3 `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html).

### Recommended starting settings

- `temperature`: `0.0` — a routing decision should be stable and reproducible ([ADR-0010](../decisions/0010-llm-model-access-strategy.md) §161 groups Delivery Targets with the low-temperature structured-output services)
- `max_tokens`: modest, since the output is a short list of targets with brief rationales
- one baseline Bedrock model across services initially, then per-service tuning later

### Access pattern

- local live mode: use the normal AWS SDK credential chain
- AWS deployment: use IAM roles for Lambda or the hosting runtime

No separate API-key layer should be introduced for a Bedrock-backed service.

## 9. Validation

The service should validate before reporting success. This is the deterministic policy validation the repo-wide contract requires — the LLM's selection must be checked against the available/eligible target set before anything downstream acts on it.

1. parse the structured model response
2. verify the response shape matches the selection schema
3. verify every selected `delivery_target` is present in the available-delivery-targets catalog
4. verify there are no duplicate targets in the selection
5. verify `selected_targets` is non-empty — an empty selection is a validation failure (this step runs only after the pre-target gate decided to continue to delivery, so a valid selection has at least one target)
6. verify `confidence` and `rationale` are present for each selected target
7. store only validated selections as successful results

These checks are hard gates ([ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) Layer A). The service must not let an unvalidated selection flow to the delivery-phase plan or the delivery layer, and it should not silently fall back to a hardcoded target set when the model output is bad — that would defeat the POC's purpose of measuring the LLM's routing capability. (The deterministic Phase 1 selection remains available as an explicit replay/stub mode per FR-DT-33, not as a hidden fallback inside the live path.)

Invalid selections should still be stored as **failed artifacts** or failed invocation records with their validation errors attached. They are valuable evidence for prompt tuning and model comparison, but they are not reusable as successful selections.

### Capability Evaluation (Layer B)

The checks above are hard gates, not a capability verdict. This service's Layer B capability evaluation — did the model select the correct target set for the scenario — is implemented as a deterministic custom metric in the shared DeepEval harness ([ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md)), scored against the frozen ADR-0013 evaluation corpus. Because the decision is set-versus-set, this is plain code (set correctness: exact match, or precision/recall over targets), not an LLM-as-judge metric, so no judge-model cost applies.

## 10. Repair Retry Mode

A **repair retry** means the model returns an invalid selection, the service feeds the validation error back to the model, and the model gets another attempt. That can be useful for experimentation, but it must not be hidden in the authoritative evaluation path, or the POC stops measuring "can the model make the routing decision in one real attempt?"

Recommended rule:

- authoritative evaluation mode: exactly one model attempt
- optional developer repair mode: explicit, off by default, separately logged

If repair retries are later explored, the service should log whether a retry was used, how many, the validation error that triggered each, and whether the final successful selection required repair.

## 11. Selection Reuse

For the POC, delivery-target selections are **execution-scoped and not stored for reuse**. Each event gets a fresh selection invocation — the selection is not looked up from a reuse store. Applicability-keyed reuse (mirroring the Workflow Actions delivery-phase plan reuse store) could be added later but is out of scope for the POC.

## 12. Observability and Evaluation Data

The service should store enough data for the team to evaluate routing quality, cost, and tuning opportunities over time. At minimum, each invocation record or stored artifact linkage should make it possible to recover:

- `execution_id`
- `event_type`
- `source_system`
- prompt-template version
- model ID
- provider
- generation settings such as temperature
- input token count when available
- output token count when available
- latency
- the raw structured model output (selected targets with per-target confidence and rationale) returned inline in the response
- the selected targets with per-target model-reported `confidence` and `rationale`
- validation outcome
- whether repair retry mode was enabled and whether it was used
- `corpus_scenario_id`, present only for invocations run against the frozen ADR-0013 evaluation corpus (absent for live production invocations), formatted as `{event_type}.{scenario_slug}.v{version}` per [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) §8

This data supports comparing prompt versions, model choices, routing-accuracy behavior, retry behavior, and cost/latency tradeoffs. This is the same per-invocation metadata contract ADR-0010 requires of every LLM Decision Service.

## 13. Suggested Module Layout

The implementation can stay small — smaller than Field Mapping, since there is no JSONata, no placeholders, and no synthesis-request artifact:

```text
delivery_targets/
  contracts.py
  prompt_templates/
    delivery_targets.v1.md
  catalogs/
    available_delivery_targets.json
  catalog_store.py
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
- `catalogs/`: committed available-delivery-targets catalog file (the ADR-0016 target set)
- `catalog_store.py`: resolve the available-delivery-targets catalog
- `prompt_builder.py`: render the system prompt and request message from event, context, and catalog
- `llm_adapter.py`: define the provider-adapter protocol and shared result shape
- `bedrock_adapter.py`: implement the provider adapter using Bedrock `Converse` plus invocation-log capture
- `replay_adapter.py`: deterministic local replay/stub without live Bedrock access (including the Phase 1 default selection, FR-DT-33)
- `validators.py`: selection-against-catalog validation (the hard gate)
- `artifact_store.py`: persist selection artifacts and failed-attempt records
- `service.py`: orchestration of resolve -> prompt -> model -> validation -> store -> response
- `api.py`: FastAPI and Lambda entrypoint boundary

## 14. Build Order

Recommended implementation order:

1. Define the transient-context-first request contract and the inline-returning response contract (selected targets with per-target confidence and rationale, plus optional storage ref).
2. Define the stored selection-artifact schema.
3. Build the committed available-delivery-targets catalog from ADR-0016.
4. Implement catalog loading.
5. Implement selection-against-catalog validation (the hard gate).
6. Add a deterministic replay/stub adapter (including the Phase 1 default selection) and fixture-driven tests.
7. Add the provider-adapter boundary, the Bedrock implementation, and the prompt template.
8. Wire the Orchestrator `select_delivery_targets` seam to the new response contract, replacing the deterministic stub.
9. Enable live Bedrock mode for prompt and model iteration.

That order keeps the service measurable and honest from the start, and keeps the stub-to-service swap at the existing Orchestrator seam a step-implementation change.

## 15. Implementation Decisions

Decisions made during pre-development design review that are not already captured in ADRs.

### Starting model

Following the Field Mapping design, a small, fast Bedrock model (for example, the Claude Haiku tier) is a reasonable starting point for this service, since routing is a constrained structured-output task. The exact invocable Bedrock model ID string (which may include a date/version suffix, per AWS's Bedrock ID format, and is typically an inference-profile-qualified id) should be verified against the current AWS Bedrock model catalog at implementation time rather than hardcoded here. The model ID should be runtime configuration so it can be changed without a code change. Per ADR-0010 §143, if routing quality is low the Workflow Actions and reasoning-heavy services are the first candidates for a larger model; Delivery Targets is a constrained task where prompt and catalog quality should be exhausted first.

### Artifact storage for local development

**File-based JSON storage** is the local development artifact storage approach, matching Field Mapping. Selection artifacts and failed-attempt records are written to and read from local JSON files keyed by a stable identifier (for example, derived from `execution_id`). This avoids a running infrastructure dependency during local development while preserving the same logical `artifact_store.py` interface that will be backed by a cloud storage layer in AWS, per [ADR-0014](../decisions/0014-poc-storage-strategy.md).
