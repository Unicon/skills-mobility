# Field Synthesis LLM Decision Service Design

Status: Draft
Date: 2026-07-16
Related: [Requirements](../2_requirements/field-synthesis-llm-decision-service.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [Orchestrator Design](./orchestrator.md) · [Field Mapping Design](./field-mapping-llm-decision-service.md) · [ADR-0007](../decisions/0007-llm-decision-service-decomposition.md) · [ADR-0008](../decisions/0008-transformation-mapping-service-decomposition.md) · [ADR-0010](../decisions/0010-llm-model-access-strategy.md) · [ADR-0013](../decisions/0013-llm-decision-service-testing-approach.md) · [ADR-0017](../decisions/0017-three-transformation-phases.md) · [ADR-0021](../decisions/0021-llm-testing-tooling-extensions.md) · [Amazon Bedrock Quickstart](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html) · [Bedrock inference prerequisites](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html) · [Bedrock structured outputs](https://docs.aws.amazon.com/bedrock/latest/userguide/structured-output.html) · [Bedrock tool use](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html) · [Boto3 Bedrock Runtime `converse`](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-runtime/client/converse.html) · [Boto3 credentials guide](https://docs.aws.amazon.com/boto3/latest/guide/credentials.html)

## 1. Overview

The **Field Synthesis LLM Decision Service** is the generative text boundary inside the transformation pipeline. Its job is to answer one question for each synthesis placeholder it receives:

`What should this human-facing field say, given only the source material identified for it?`

Per ADR-0017, the default expected transformation path runs as three sequential phases (`credential_template` → `issuer_payload` → `wallet_payload`), each of which may apply the internal `field mapping → field synthesis → JSONata execution` pattern. Field Synthesis is **phase-specific, not universally mandatory** (ADR-0017): it runs only in phases whose Field Mapping result carries synthesis placeholders. In the default POC path that is:

| Phase | `transformation_type` | Input | Generated content |
| --- | --- | --- | --- |
| Phase 1 (credential-level) | `credential_template` | Synthesis briefs from the phase's Field Mapping result | Credential-level field values: achievement descriptions, alignment rationale, skill summaries |
| Phase 2 (learner-level) | `issuer_payload` | Synthesis briefs from the phase's Field Mapping result | Learner-level field values: assignment summaries, evidence narratives |

The `wallet_payload` phase is usually purely structural and skips synthesis (no synthesis-request artifact is produced for it). The same service handles every invocation — up to three per first-seen execution — with no phase-specific variants; only the inputs differ.

## 2. What the Service Produces

The service produces one stored artifact per invocation: a **synthesis result artifact** containing the generated text for every requested `placeholder_id`.

### Stored synthesis result artifact

Recommended shape:

```json
{
  "synthesis_result_schema_version": "v1",
  "transformation_type": "issuer_payload",
  "execution_id": "exec_123",
  "values": {
    "achievement_description": "Learners who complete this course demonstrate proficiency in applying computational thinking to data analysis problems, including algorithm design and structured problem decomposition.",
    "skills_alignment_summary": "This achievement aligns to O*NET 15-1252.00 (Software Developers) skill cluster 2.A.1.e: Mathematical Reasoning."
  },
  "confidence": 0.84,
  "rationale": "Source material contained clear course objectives and rubric descriptions; skills alignment required inferential grounding from course learning outcomes."
}
```

The `values` map is a flat `{ "<placeholder_id>": "<generated text>" }` keyed exactly by the `placeholder_id` values from the incoming synthesis request. No extra keys are permitted; no requested key may be absent.

The Transformation Executor merges the synthesis result under the `synthesized` namespace in the JSONata execution context before running the mapping artifact:

```json
{
  "source_payloads": {
    "learner_context": { "...": "..." },
    "credential_template": { "...": "..." }
  },
  "synthesized": {
    "achievement_description": "...",
    "skills_alignment_summary": "..."
  }
}
```

This is the same merge convention defined in the Field Mapping design (§2). Field Synthesis's `values` map is what the Transformation Executor puts under `synthesized`.

### Immediate service response

The synchronous response to the Orchestrator returns `values`, `confidence`, and `rationale` inline always:

```json
{
  "status": "succeeded",
  "values": {
    "achievement_description": "...",
    "skills_alignment_summary": "..."
  },
  "confidence": 0.84,
  "rationale": "Source material contained clear course objectives and rubric descriptions; skills alignment required inferential grounding from course learning outcomes.",
  "synthesis_result_ref": "synthesis_result:456",
  "llm_invocation_log_ref": "llmcall:789"
}
```

`values` is a handful of text fields — small enough that withholding it behind a ref adds round-trip latency with no benefit. `synthesis_result_ref` is an optional storage-correlation pointer; the Orchestrator or Transformation Executor may pass it downstream to locate the persisted artifact, but the Transformation Executor does not need to resolve the ref to get the `values` map — it is already in the response. `llm_invocation_log_ref` points to the detailed per-invocation metadata in execution logs.

## 3. Runtime Shape

The recommended runtime flow is:

```text
Orchestrator
  -> Field Synthesis boundary
      -> accept synthesis-request artifact (by ref or inline)
      -> resolve the stored synthesis-request artifact when provided by ref
      -> screen source_payloads in each brief for prompt injection
      -> build Bedrock request payload (one request covering all placeholders)
      -> call Bedrock
      -> parse structured output
      -> validate coverage (every placeholder_id answered, no extras)
      -> store synthesis result artifact
      -> return values/confidence/rationale inline + synthesis_result_ref to Orchestrator
```

Two boundaries matter:

- the service resolves **its own stored artifacts** (the synthesis-request artifact) when given a ref
- the service does **not** perform live source-system fetches — all source material arrives in the synthesis briefs

## 4. Request Contract

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "transformation_type": "issuer_payload",
  "synthesis_request_ref": "synthesis:456"
}
```

When `synthesis_request_ref` is provided, the service loads the stored synthesis-request artifact from the artifact store. For local development and testing, the Orchestrator may supply the artifact inline instead:

```json
{
  "execution_id": "exec_123",
  "event_id": "evt_123",
  "transformation_type": "issuer_payload",
  "synthesis_request": {
    "synthesis_request_schema_version": "v1",
    "transformation_type": "issuer_payload",
    "requests": [
      {
        "placeholder_id": "achievement_description",
        "target_path": "achievement.description",
        "source_payload_paths": [
          "source_payloads.learner_context.course.description"
        ],
        "source_payloads": {
          "learner_context": {
            "course": {
              "description": "..."
            }
          }
        },
        "instruction": "Write a concise achievement description grounded only in the selected source content."
      }
    ]
  }
}
```

The `synthesis_request` inline form is a fallback for development convenience, not the default orchestration contract. Prompt templates, model IDs, and temperatures are service configuration, not business inputs on the request.

`transformation_type` is present on the request (not only on the loaded artifact) so the service can route and log correctly before resolving the ref.

## 5. Synthesis Brief Structure

Each synthesis brief in the `requests` array carries everything the service needs to generate one placeholder's value:

| Field | Purpose |
| --- | --- |
| `placeholder_id` | The key for this value in the result `values` map |
| `target_path` | The credential target field being satisfied (informational; aids prompt clarity) |
| `source_payload_paths` | JSONPath-style references into the original source payload set identifying which fields contributed to this brief |
| `source_payloads` | Concrete snapshot of the values found at `source_payload_paths` — the authoritative source material for this synthesis task |
| `instruction` | Field-specific guidance on what to generate and any implied constraints on length or tone |

At least one of `source_payloads` (concrete snapshot) or `source_payload_paths` (references) MUST be present. If both are present, `source_payloads` is the snapshot of the values at those paths and is the concrete material the model uses for generation. `source_payload_paths` is informational provenance.

The service does NOT re-fetch or re-assemble source data from paths. It uses `source_payloads` as given.

## 6. Grounding Constraint

Faithfulness to the supplied source material is the central quality property of this service. The model must generate text that derives only from the content present in each brief's `source_payloads`.

This constraint operates at three levels:

- **Prompt level:** The system prompt and request message together must make the grounding boundary explicit. The model must be told it is working from a provided excerpt only, must not consult prior knowledge about the institution, course, or learner beyond what is supplied, and must not introduce entities, statistics, or claims that do not appear in the source material.
- **Validation level (Layer A):** Coverage validation (placeholder_id completeness) is a hard gate. Grounding validation is harder to enforce deterministically; it is addressed at Layer B.
- **Evaluation level (Layer B):** The DeepEval G-Eval metric for this service SHALL include a faithfulness/groundedness criterion scored against the `source_payloads` for each placeholder. This is the primary quality question for the POC for this service.

The grounding constraint has an important asymmetry: a missing fact from the source material is a valid omission; an invented fact not present in the source material is a failure. The prompt must communicate this.

## 7. LLM Invocation and Prompting Strategy

The initial implementation should make **one Bedrock Converse request** for each Field Synthesis invocation, covering all placeholders in the synthesis request together.

That one request should contain:

- one **system prompt** template file that defines the service role and the grounding rule
- one **request message** assembled from all synthesis briefs in the current invocation
- one **structured-output schema** that constrains the model's response to the `values` map plus `confidence` and `rationale`

### Bedrock request inputs

The request message should include, in structured or clearly delimited form:

- `transformation_type`
- for each placeholder brief: `placeholder_id`, `target_path`, `instruction`, and `source_payloads`

### Bedrock response output

The model response should be constrained to a schema that includes at minimum:

- `values`: the flat `{ "<placeholder_id>": "<generated text>" }` map
- `confidence`
- `rationale`

### Prompt content

The system prompt and request message together should tell the model:

- it is generating human-facing text for specified credential fields
- for each field, it must work only from the source material provided in that field's brief
- it must not introduce facts, claims, or entities not present in the supplied source material
- the `instruction` for each field must be respected, including any length or framing constraints
- it must generate a value for every `placeholder_id` present and must not add others

### Prompt tuning emphasis

Prompt tuning for this service will likely focus on:

- reinforcing the grounding boundary without making the text sound mechanical or over-hedged
- balancing brevity with completeness for each field type (a credential description has different norms than an alignment rationale)
- handling briefs where the source material is thin — the model must produce a useful value without fabricating

Prompt templates should live in version-controlled files so changes can be reviewed and compared against the evaluation corpus.

### Multi-placeholder batching

Covering all placeholders in one Bedrock call is the default. This keeps latency and cost low. A later experiment may split into one call per placeholder if the model conflates source material across briefs. The default should remain one call until testing shows a concrete reason to split.

## 8. Bedrock Invocation Design

### Primary platform

Amazon Bedrock is the POC's primary managed inference platform per ADR-0010. As with the sibling services, Field Synthesis should interact with models through a **thin provider adapter** rather than embedding Bedrock-specific request construction throughout service logic.

For the POC, the adapter should target Bedrock's **Converse API** with schema-constrained structured output via the `toolUse` feature, exactly as the sibling services do.

For this service, the Bedrock interaction sequence is:

1. screen free-text values in each brief's `source_payloads` for prompt-injection attempts (ADR-0021) before they reach the prompt
2. build the prompt and structured-output schema
3. call the provider adapter, which invokes Bedrock `Converse` through the AWS SDK
4. parse the returned structured object
5. validate coverage (every `placeholder_id` answered, no extras)
6. store the synthesis result artifact

### Recommended starting settings

- `temperature`: see §17 (Implementation Decisions) — a low but non-zero value is recommended; not copied blindly from Field Mapping's `0.0`
- `max_tokens`: high enough to return all generated values for the largest expected synthesis request (multiple placeholders, each potentially a paragraph)
- one baseline Bedrock model across services initially, then per-service tuning later; Field Synthesis is the task type most likely to benefit from a Sonnet-class model if Haiku-class quality is insufficient (ADR-0010)

### Access pattern

- local live mode: use the normal AWS SDK credential chain
- AWS deployment: use IAM roles for Lambda or the hosting runtime

No separate API-key layer should be introduced for a Bedrock-backed service.

## 9. Response Contract

The synchronous response returns generated content inline always:

```json
{
  "status": "succeeded",
  "values": {
    "achievement_description": "...",
    "skills_alignment_summary": "..."
  },
  "confidence": 0.84,
  "rationale": "...",
  "synthesis_result_ref": "synthesis_result:456",
  "llm_invocation_log_ref": "llmcall:789"
}
```

`values`, `confidence`, and `rationale` are always present. `synthesis_result_ref` is an optional storage-correlation pointer the Orchestrator may pass downstream; the Transformation Executor extracts the `values` map from this response directly rather than resolving a ref. `llm_invocation_log_ref` points to detailed per-invocation metadata (token counts, latency, model ID) in execution logs — those fields do not belong in the synchronous response.

## 10. Validation

The service should validate before reporting success:

1. parse the structured model response
2. verify that the result contains a `values` entry for every `placeholder_id` in the synthesis request — no missing keys
3. verify that the `values` map contains no keys that were not in the synthesis request — no extra keys
4. verify that `confidence` and `rationale` are present
5. store only validated artifacts as successful results

This service does not validate the semantic grounding of generated text at Layer A — that check is not feasibly deterministic. Grounding is the primary concern at Layer B evaluation (§11). The service must not silently return empty or stub values for failed placeholders; failed invocations must be stored as failure records with their validation errors attached, not as partial successes.

### Capability Evaluation (Layer B)

The Layer A checks above are hard gates, not a capability verdict. Field Synthesis's Layer B capability evaluation — whether the generated text is grounded, useful, and free of fabrication — is implemented using the shared DeepEval test harness (ADR-0021) with a **G-Eval metric**, as this is the one genuinely open-ended generative service. The G-Eval criteria should include at minimum:

- **Groundedness:** does the generated text derive only from the supplied `source_payloads`?
- **Relevance:** is the generated text appropriate for the target credential field?
- **Non-fabrication:** are there claims in the generated text not supported by the source material?

This contrasts with Field Mapping's Layer B, which uses a deterministic custom metric against a human-authored canonical mapping. Field Synthesis uses a judgment-based metric because exact-match comparison is not meaningful for open-ended natural language output. Per ADR-0021, G-Eval output is developer-convenience evidence and triage; it is not the authoritative verdict for the POC's final conclusion. The authoritative evaluation for Field Synthesis is human rubric review per ADR-0013.

## 11. Repair Retry Mode

A **repair retry** for this service would mean feeding a failed validation back to the model for another generation attempt.

The same rule applies as for the sibling services:

- authoritative evaluation mode: exactly one model attempt
- optional developer repair mode: explicit, off by default, separately logged

If repair retry is ever added for this service, it should log at minimum:

- whether a retry was used
- how many retries were used
- the validation error (typically a coverage failure — missing or extra placeholder) that triggered the retry
- whether the final successful result required repair

Semantic grounding failures (detected at Layer B, not Layer A) are not a retry trigger for the authoritative evaluation path; they are evaluation evidence, not runtime errors.

## 12. Observability and Evaluation Data

The service should store enough data for the team to evaluate output quality, cost, and tuning opportunities over time. This mirrors the Field Mapping service's observability requirements (design §14) applied to the synthesis task.

At minimum, each invocation record or stored artifact linkage should make it possible to recover:

- `execution_id`
- `transformation_type`
- `placeholder_id` set from the synthesis request
- prompt-template version
- model ID
- provider
- generation settings including temperature
- input token count when available
- output token count when available
- latency
- the raw structured model output or a stable reference to where it is stored
- model-reported `confidence`
- model-reported `rationale`
- validation outcome (coverage pass/fail)
- whether repair retry mode was enabled and whether it was used
- `corpus_scenario_id`, present only for invocations run against the frozen ADR-0013 evaluation corpus (absent for live invocations), formatted as `{event_type}.{scenario_slug}.v{version}` per ADR-0013 §8

This data is necessary for comparing prompt versions, model choices, per-placeholder quality trends, and cost-latency tradeoffs across the POC.

## 13. Suggested Module Layout

The implementation can stay small, mirroring Field Mapping's structure without the catalog and JSONata concerns:

```text
field_synthesis/
  contracts.py
  prompt_templates/
    field_synthesis.v1.md
  llm_adapter.py
  bedrock_adapter.py
  replay_adapter.py
  validators.py
  artifact_store.py
  service.py
  api.py
```

Responsibilities:

- `contracts.py`: request/response schemas, synthesis-brief schema, synthesis-result artifact schema
- `prompt_templates/`: versioned system prompt and request message templates; changes here trigger Layer D regression per ADR-0013
- `llm_adapter.py`: define the provider-adapter protocol and shared result shape (same protocol as Field Mapping's adapter — implementations are interchangeable per ADR-0010)
- `bedrock_adapter.py`: implement the provider adapter using Bedrock `Converse` with schema-constrained structured output via `toolUse`; capture per-invocation metadata per ADR-0010 §60
- `replay_adapter.py`: implement deterministic local replay without live Bedrock access; consume committed fixture responses keyed by synthesis-request artifact hash or scenario ID
- `validators.py`: coverage validation (placeholder_id completeness), response-schema validation
- `artifact_store.py`: persist synthesis-request artifacts (loaded by ref) and synthesis-result artifacts; same logical interface as Field Mapping's store
- `service.py`: orchestration of load → screen → prompt → model → validate → store → response
- `api.py`: FastAPI and Lambda entrypoint boundary; port 8150

## 14. Build Order

Recommended implementation order, mirroring Field Mapping's build sequence adapted for synthesis:

1. Define the synthesis-request artifact schema (Field Mapping's output; Field Synthesis's input). These are related artifacts — coordinate schema versions across the two services.
2. Define the synthesis-result artifact schema and the compact response contract.
3. Build the artifact store: load synthesis-request artifacts by ref; persist synthesis-result artifacts.
4. Implement coverage validation.
5. Add a deterministic replay adapter and fixture-driven tests (Layer A gates must pass before any model work begins).
6. Add the provider-adapter boundary and the Bedrock implementation with the prompt templates and per-invocation metadata capture.
7. Wire the Orchestrator seam: accept `synthesis_request_ref` from Field Mapping's response; pass the inline `values` (plus `synthesis_result_ref` for storage correlation) to the Transformation Executor.
8. Enable live Bedrock mode for prompt iteration and Layer B evaluation runs.

That order ensures the service is testable and contracts are stable before any live Bedrock work begins.

## 15. Port

Field Synthesis listens on **port 8150** for local development.

Sibling services for reference: Field Mapping at 8120, Delivery Targets at 8130, Workflow Actions at 8140. Consul occupies 8300–8302, 8500, and 8600.

## 16. Implementation Decisions

Decisions made during pre-development design review that are not already captured in ADRs.

### Temperature

**Recommended starting range: 0.3 – 0.5 (per ADR-0010), starting at 0.3.**

This is a deliberate design decision, not a copy of Field Mapping's `0.0`. Field Mapping uses `0.0` because its output (JSONata) must be syntactically reproducible and structurally precise. Field Synthesis produces human-facing natural language for credential fields such as achievement descriptions and assignment summaries. For this task:

- a temperature of `0.0` would produce mechanically consistent but potentially monotonous text; repeated invocations on the same scenario would return identical output, which does not reflect the variance a human reviewer might see in production
- a non-zero temperature introduces variety consistent with the generative task and avoids worst-case mode collapse where the model always picks the statistically safest phrasing

The tension with deterministic replay is real: the replay adapter must return committed fixture responses regardless of temperature, so replay behavior is always deterministic. Live Bedrock mode with a non-zero temperature means two live invocations on the same input may return different text — this is expected and acceptable for a generative service, and it is why the Layer B evaluation uses G-Eval criteria (groundedness, relevance, non-fabrication) rather than exact-match comparison.

ADR-0010 §Open Questions recommends Field Synthesis start at 0.3–0.5. The lower end of that range (0.3) is the recommended POC starting point to balance variety with coherence. Temperature is runtime configuration — it must be tunable without a code change, and Layer D regression runs should record the temperature used so prompt-comparison results are interpretable.

### Starting model

**Claude Haiku 4.5** is the starting model, consistent with the sibling services. Field Synthesis is the task type (ADR-0010) where a Sonnet-class model most clearly outperforms Haiku-class on quality visible to human reviewers. If Layer B evaluation shows systematically weak groundedness or low rubric scores, upgrading to Claude Sonnet via the provider adapter is the recommended first escalation — no code change required.

The exact invocable Bedrock model ID string should be verified against the current AWS Bedrock model catalog at implementation time.

### Artifact storage for local development

**File-based JSON storage** is the local development approach, mirroring Field Mapping. Synthesis-result artifacts are written to and read from local JSON files keyed by Field Mapping's **`stable_key`** — the same identifier that already governs the mapping and synthesis-request artifacts. The incoming `synthesis_request_ref` is formatted as `synthesis:<stable_key>`, so the service can extract `<stable_key>` directly from the ref it receives without recomputing it. Synthesis-result artifacts are stored under that same key (for example, as `synthesis_result:<stable_key>`), co-locating all three artifact kinds (mapping, synthesis-request, synthesis-result) under one shared key. Keying off `execution_id` would make result reuse (FR-FS-21) structurally impossible, since `execution_id` is unique per run. The same logical `artifact_store.py` interface backs both local and cloud storage.

### One Bedrock call per invocation (all placeholders together)

All placeholders in one synthesis request are covered in a single Bedrock call. This keeps per-loop cost and latency low. If quality testing reveals the model conflates source material across briefs when they are batched, a per-placeholder call mode can be added as an opt-in configuration without changing the request or response contract.

### Synthesis-request artifact as the input contract

The service treats the synthesis-request artifact produced by Field Mapping as its canonical input contract, not a bespoke Field-Synthesis-specific request format. This keeps the two services' contracts tightly coupled by design: the output of Field Mapping's `synthesis_request_schema_version: v1` is the input of Field Synthesis without translation. Schema version changes on either side require a coordinated update.
