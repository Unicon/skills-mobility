# 0013. LLM Decision Service Testing Approach

- Status: Proposed
- Date: 2026-07-04

> **Note (2026-06-25):** This ADR scopes the evaluation corpus and scorecard to the two loops defined in ADR-0008. ADR-0017 introduces a third transformation phase for the primary POC path. References to "Loop 1 and Loop 2" and "both transformation loops" in this ADR should be read as the historical two-loop baseline; the evaluation corpus and per-phase scorecard rows will need to be extended accordingly.

## Context

ADRs 0007, 0008, and 0009 define **four LLM Decision Service types** in the POC:

1. **Workflow Actions** — generates the abstract orchestration plan
2. **Delivery Targets** — selects downstream delivery targets
3. **Field Mapping** — generates JSONata mappings and synthesis placeholders
4. **Field Synthesis** — generates human-facing synthesized field values

On a first-seen workflow, these four service types account for up to **six LLM invocations**:

- Workflow Actions: 1
- Delivery Targets: 1
- Field Mapping: 2 (credential-template loop and learner-level loop)
- Field Synthesis: 2 (credential-template loop and learner-level loop)

The core question of this POC is not merely whether the end-to-end demo can complete. It is whether LLMs can actually perform the jobs assigned to these four service types well enough to justify the architecture.

Neither of the two obvious testing shortcuts answers that question:

- **End-to-end happy-path testing alone is insufficient.** A workflow can still complete if deterministic validation catches bad outputs, if caches bypass an LLM step, or if only the easiest scenarios are exercised.
- **Schema-only or unit-style testing alone is insufficient.** A JSON response can be structurally valid while still making a poor routing decision, a weak plan, or a useless badge description.

The testing approach therefore needs to distinguish two different concerns:

1. **Service capability** — did the LLM perform its assigned decision-making task correctly or acceptably for this scenario?
2. **System safety** — did the deterministic architecture validate, constrain, and audit the output correctly even when the LLM was imperfect?

That distinction matters especially because:

- The transformation path includes reusable artifacts such as stored plans, stored credential templates, and stored mapping specifications. Those caches are valuable operationally, but they can hide whether the LLM could do the job on the uncached path.
- The four service types produce very different outputs. Workflow plans, delivery-target selections, JSONata mappings, and human-facing synthesized text cannot be judged with one shared metric.
- The POC currently keeps source-data fetching deterministic in the Context Builder and defers a first-class MCP client layer. That makes it practical to freeze evaluation inputs and compare runs consistently.
- Pending model-access work proposes logging per-invocation metadata such as model ID, latency, token counts, confidence, and rationale. That metadata is useful only if the POC has a defined evaluation method that interprets it.

## Decision Drivers

- Produce a credible answer to "can AI do this job?" for each of the four LLM service types
- Keep the evaluation repeatable across prompt and model changes
- Separate service-quality evidence from guardrail/safety evidence
- Allow different evaluation methods for structured outputs vs. open-ended text
- Keep the testing scope small enough for a POC while still covering the important workflow branches
- Reuse the project's committed-fixture approach so evaluation inputs remain deterministic and auditable

## Decision

The POC will evaluate the four LLM Decision Service types using a **frozen evaluation corpus**, **service-specific scorecards**, and **layered testing**. The authoritative evidence for LLM quality will come from service-level evaluation on the uncached path, not from end-to-end demos alone.

### 1. Frozen Evaluation Corpus

The project will maintain a committed evaluation corpus for LLM testing. Each case in the corpus should freeze the inputs needed to evaluate one scenario consistently, including:

- source event fixture
- normalized context bundle assembled for the relevant service
- relevant policy context
- available delivery targets and target metadata
- relevant target schema or plan/action-registry inputs
- expected outcome contract for the scenario

For the POC, the corpus should cover at minimum:

- each event type named in the POC requirements
- at least one straightforward positive delivery path
- the no-delivery / early-termination cases already identified in ADR 0009
- delivery outcomes covering both target systems, a single target, and neither target
- both transformation loops defined in ADR 0008

Because the Context Builder remains deterministic and MCP is currently deferred, the corpus can freeze context bundles directly rather than relying on live tool discovery or external runtime lookups.

### 2. Uncached Service-Capability Runs Are Authoritative

Official evaluation of LLM capability must exercise the **uncached path**:

- no plan reuse for Workflow Actions
- no template reuse for Loop 1 evaluation
- no stored mapping reuse for Field Mapping evaluation

Cache-hit behavior should still be tested separately at the integration level, but it does **not** count as evidence that the LLM itself can do the job.

### 3. Layered Testing

The testing approach has four layers.

#### Layer A. Contract and Hard-Gate Tests

Every evaluated LLM output must first pass its deterministic contract checks:

- output schema is valid
- `confidence` and `rationale` are present
- only approved targets, actions, or step types are referenced
- JSONata parses and executes where applicable
- no unresolved placeholders or structurally invalid payload fragments remain
- if the Policy Rules Service is implemented in time for the POC, the relevant output also passes policy validation

These checks do not prove the output is good, but failing them is an immediate failure for the scenario.

#### Layer B. Service-Level Capability Evaluation

Each of the four service types is then judged against a service-specific scorecard.

| Service type | Hard gates | Primary capability judgment | Authoritative reviewer |
| --- | --- | --- | --- |
| Workflow Actions | Plan schema valid; only approved action IDs/step types; passes Policy Rules validation if that service is implemented | Match against the canonical expected plan for the scenario, including expected terminal outcome and required or forbidden major steps | Deterministic comparator against the canonical scenario plan |
| Delivery Targets | Output schema valid; only known targets referenced | Exact match on selected target set for the scenario | Deterministic comparator |
| Field Mapping | Mapping spec schema valid; JSONata parses; placeholder structure valid; passes policy validation if implemented | Functional correctness of the executed result plus semantic correctness of the source-to-target field alignment and JSONata logic relative to a human-authored canonical mapping | Deterministic execution + comparator against canonical human mapping, with human review when semantic alignment is unclear |
| Field Synthesis | Output schema valid; all requested synthesis fields returned | Groundedness, usefulness for the target field, and absence of fabrication | Human rubric review |

The scorecards should be interpreted as follows:

- **Workflow Actions** should default to comparison against a canonical expected plan per scenario. For this POC, that is a more useful standard than assuming many plans are equally acceptable. If we later discover truly equivalent variants that differ only trivially in structure, those variants can be added explicitly to the allowed scenario contract rather than treated as open-ended alternatives.
- **Delivery Targets** is a small-output classification task. The selected target set should match exactly. The useful error analysis is false-positive targets and false-negative targets, not a blended partial-credit score.
- **Field Mapping** is judged on two dimensions. First, the generated JSONata and placeholder structure must function correctly when executed. Second, the mapping logic itself must align with a human-authored canonical mapping of source fields to target fields and expressions. Exact string equality of the JSONata is still not required: two different expressions may be acceptable if both are functionally correct and semantically aligned to the canonical mapping intent.
- **Field Synthesis** is the only service whose primary judgment is qualitative. It should be reviewed against a simple rubric that asks whether the text is grounded in the provided source material, appropriate for the target field, and free of obvious fabrication or contradiction.

Field Mapping and Field Synthesis must be scored **separately for Loop 1 and Loop 2**, even though the final verdict is per service type. The POC needs to know whether a service works equally well for credential-template generation and learner-level record generation.

Institution-specific interpretations that go beyond the agreed source and target field descriptions are out of scope for the initial POC unless those interpretations are explicitly captured in the canonical mapping used for evaluation.

#### Layer C. End-to-End Workflow Evaluation

Representative scenarios must also run through the full orchestration path:

- event ingress
- context assembly
- Workflow Actions planning
- Delivery Targets selection
- Transformation loop(s)
- Policy Rules validation, if implemented
- delivery adapter execution
- audit trace capture

These end-to-end runs answer a different question from the service scorecards: whether the guarded system behaves correctly as a whole. They are required, but they are supporting evidence rather than the primary basis for judging LLM capability.

#### Layer D. Regression and Model/Prompt Comparison

The same frozen corpus must be rerun whenever any of the following change:

- prompt template
- model ID
- provider adapter
- output schema
- deterministic comparator or policy contract affecting interpretation

Regression results should be compared by service type, not collapsed into one blended "LLM accuracy" number.

### 4. Confidence Scoring Is Measured, Not Trusted

Confidence is required output for every service, but it is **not** itself proof of quality. The POC should evaluate confidence in a secondary scorecard:

- do correct outputs tend to have higher confidence than incorrect ones?
- are some services systematically overconfident?
- does confidence help separate acceptable outputs from unacceptable ones?

The POC should treat confidence as an observed signal to analyze, not a metric to optimize blindly.

### 5. Human Review Is Targeted and Bounded

Human review should be used only where deterministic comparison is insufficient:

- primary review for Field Synthesis
- authorship and maintenance of the canonical mapping used to score Field Mapping
- adjudication for Field Mapping only when the executed output is acceptable but semantic alignment to the canonical mapping is unclear
- Workflow Actions adjudication only if the team later decides to allow explicitly-defined near-equivalent plan variants rather than one canonical plan per scenario

LLM-as-judge may be used as a developer convenience for triage, clustering, or drafting review notes, but it is **not** the authoritative scorer for the POC's final conclusions.

### 6. Policy Rules Validation Is Additive, Not Foundational to the Evaluation Method

The evaluation method in this ADR does **not** depend on the Policy Rules Service being fully implemented in time for the POC. The service-level capability tests, canonical comparisons, and end-to-end workflow runs still provide meaningful evidence without it.

If the Policy Rules Service is implemented, its results become additional **system-safety evidence**:

- whether bad plans are rejected
- whether invalid routing decisions are blocked
- whether invalid mappings or payloads are caught before delivery

That is valuable, but it should not be confused with the primary question of whether the LLM Decision Services themselves performed their assigned jobs well.

### 7. Final POC Verdict Is Per Service Type

The POC should conclude with a separate verdict for each of the four service types. It should not produce only one overall "AI worked" or "AI failed" statement.

Each service type should receive one of three verdicts:

- **Viable for the POC** — passes hard gates consistently and meets its service-specific quality bar on the representative corpus
- **Promising but not yet reliable** — structurally safe enough to keep experimenting with, but capability is too inconsistent to claim success
- **Not viable in current form** — repeatedly fails hard gates or produces unacceptable outputs even after reasonable prompt/model iteration

The exact numeric thresholds for those verdicts should live alongside the evaluation harness rather than in this ADR, but the verdict categories themselves are part of the architecture decision.

### 8. Evaluation Corpus Storage, Format, and Versioning

This ADR originally left the corpus's repo location and fixture versioning as an open question. This section resolves it.

**Location.** The corpus will live in a new uv workspace member, `libs/eval-corpus`, mirroring `libs/events`'s pattern exactly: its own `pyproject.toml`, `src/` layout, hatchling build. Per ADR-0001, `libs/` holds shared Python libraries reused by multiple services. No single service owns this corpus: the Workflow Actions, Delivery Targets, Field Mapping, and Field Synthesis test suites all read from it, and ADR-0001's dependency rules forbid one `services/` package from depending on another, which rules out bundling the corpus inside any one service's own package.

**Format and granularity.** The corpus holds one directory per scenario under `scenarios/`, for example `scenarios/skill_mastered.dual_target/`. Each scenario directory has a small `scenario.yaml` index of scalar fields and relative file references, plus sibling frozen JSON/Markdown payload files for anything large: the event fixture, the context bundle, the canonical mapping per phase, rubric notes, and so on. This follows the Context Builder fetch-profile precedent (`services/context-builder/src/context_builder/fetch_profiles/*.yaml`: hand-authored, one file per named thing, reviewable diffs) rather than the Mock LMS `catalog.json` precedent (machine-generated bulk seed data). The corpus is small and hand-curated by design (§1 above), and splitting large bodies into sibling files keeps each `scenario.yaml` reviewable instead of becoming one unreadable YAML wall per scenario.

**Identifier and versioning.** Each scenario is identified by `corpus_scenario_id = {event_type}.{scenario_slug}.v{version}`, for example `skill_mastered.dual_target.v1`. This extends the Context Builder's `{name}.v{version}` pattern (design doc §5) with a `scenario_slug` segment: this corpus needs multiple scenarios per event type (delivery-outcome combinations, edge cases), while Context Builder has exactly one fetch profile per event type. `version` is an integer bumped in place on change; git history is the changelog. Filenames and directory names omit the version (`scenarios/skill_mastered.dual_target/`, not a `v1`-suffixed directory), matching the fetch-profile convention where only the internal `id`/`version` fields carry it.

**Scenario shape.** A scenario's `scenario.yaml` has a shared `input` section and an `expected` section keyed by service:

```yaml
id: skill_mastered.dual_target.v1
event_type: skill_mastered
scenario_slug: dual_target
version: 1

input:
  source_event_fixture: source_event.json
  context_bundle: context_bundle.json
  policy_context: policy_context.json
  available_delivery_targets:
    - target_id: learncard_issuer
      metadata_ref: delivery_targets/learncard_issuer.json
    - target_id: learncard_wallet
      metadata_ref: delivery_targets/learncard_wallet.json
  target_schemas:                     # credential_template has no delivery_target (ADR-0017);
    credential_template: target_schemas/credential_template.json  # issuer/wallet are keyed by target below
    issuer_payload:
      learncard_issuer: target_schemas/issuer_payload.learncard_issuer.json
    wallet_payload:
      learncard_wallet: target_schemas/wallet_payload.learncard_wallet.json
  action_registry_snapshot: action_registry_snapshot.json

expected:
  workflow_actions:
    canonical_plan: expected/workflow_actions/canonical_plan.json
    terminal_outcome: delivered
    required_steps: [classify_skill_mastered, resolve_delivery_targets]
    forbidden_steps: [terminate_early]
  delivery_targets:
    canonical_target_set: [learncard_issuer, learncard_wallet]
  field_mapping:
    credential_template:
      canonical_mapping: expected/field_mapping/credential_template.jsonata
      field_classifications: expected/field_mapping/credential_template.classifications.json
    issuer_payload:
      learncard_issuer:
        canonical_mapping: expected/field_mapping/issuer_payload.learncard_issuer.jsonata
        field_classifications: expected/field_mapping/issuer_payload.learncard_issuer.classifications.json
    wallet_payload:
      learncard_wallet:
        canonical_mapping: expected/field_mapping/wallet_payload.learncard_wallet.jsonata
        field_classifications: expected/field_mapping/wallet_payload.learncard_wallet.classifications.json
  field_synthesis:
    credential_template:
      fields: [badge_description]
      rubric_notes: expected/field_synthesis/credential_template.rubric.md
    issuer_payload:
      learncard_issuer:
        fields: [badge_description]
        rubric_notes: expected/field_synthesis/issuer_payload.learncard_issuer.rubric.md
    # wallet_payload has no entry here: synthesis_allowed is false for wallet-phase requests
    # (design doc §6), so Field Synthesis is never exercised for wallet targets
```

`field_mapping` and `field_synthesis` key `issuer_payload` and `wallet_payload` by the specific `delivery_target` they apply to, not just the phase name, because the canonical answer is target-specific: adding a second wallet target such as SmartResume would add a sibling `smart_resume` key alongside `learncard_wallet` under `field_mapping`'s `wallet_payload` (still with no counterpart under `field_synthesis`, since synthesis is not exercised for wallet targets regardless of which wallet), while every other part of the scenario is unaffected. `credential_template` has no target-keyed layer since it has no `delivery_target` (ADR-0017).

`target_schemas` and `action_registry_snapshot` are frozen snapshots owned by the scenario, not live references into a service's own catalog. This matches §1's existing reasoning for freezing context bundles: it keeps Layer D regression deterministic and reproducible. A live reference would also violate ADR-0001's rule that `libs/` must not depend on `services/`, and it would let catalog drift silently reinterpret old frozen scenarios.

**Scaffolding.** This decision documents the target shape only. No `libs/eval-corpus/pyproject.toml` and no real scenario files are being created as part of it; it is left for whoever first needs Layer B evaluation to build against, the same treatment FR-FM-5a already gives Field Mapping's own catalog files ("does not pre-exist and must be authored during implementation").

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| End-to-end demo testing only | Judge success by whether representative workflows complete | Conflates LLM capability with deterministic guardrails, caches, and adapter behavior; weak evidence for whether the LLMs did their jobs |
| Contract/schema testing only | Judge success by structured-output validity and basic execution checks | Misses the real question of decision quality; valid JSON can still be a bad plan, bad routing choice, or weak synthesized text |
| Fully automated scoring, including LLM-as-judge | Use automated validators plus LLM scoring for all services | Circular and difficult to defend for the POC's main research question, especially for the human-facing content tasks |
| Frozen corpus + service-specific scorecards + targeted human review (chosen) | Combine deterministic checks, service-level capability evaluation, and limited human review where needed | Requires some manual rubric design and review effort, and the corpus must be curated carefully to avoid overfitting to trivial cases |

## Why This Approach

### The POC needs service-level evidence, not just system-level evidence

The architecture deliberately separates Workflow Actions, Delivery Targets, Field Mapping, and Field Synthesis because they are different decision problems. The testing approach needs to preserve that separation. A single end-to-end pass/fail signal would throw away the most valuable information the POC is supposed to produce.

### Caches are useful operationally but misleading evaluatively

ADR 0008 and ADR 0009 both introduce reuse opportunities. Those are desirable features of the final system, but they cannot be allowed to mask whether the uncached LLM path is actually good enough. Testing the uncached path as the authoritative capability measure keeps the conclusion honest.

### Different service types need different evaluators

Delivery target selection can be judged deterministically. Field Mapping is a hybrid case: deterministic execution matters, but human-authored canonical mappings are also needed to judge whether the source-to-target alignment logic is actually the right one. Human-facing synthesized text cannot be judged credibly by exact string matching. Using one evaluation method for all four services would either over-automate the semantic cases or over-manualize the structured ones.

### Functional equivalence is necessary but not sufficient for generated mappings

For Field Mapping, the real artifact is not just the literal JSONata string; it is the mapping decision embodied in that JSONata. Two different expressions can be equally correct, so exact string comparison would create false failures. But execution alone is not enough either, because a mapping can appear to work on a narrow fixture while still being conceptually wrong. The right evaluation is therefore a combination of executed-result validation and comparison to a human-authored canonical mapping.

### Frozen inputs are practical because the POC keeps the upstream context deterministic

Since source-data fetching is deterministic and a first-class MCP client layer is deferred, the POC can freeze the service inputs in committed fixtures and rerun them consistently. That gives the evaluation harness stable, comparable evidence.

## Consequences

### Positive

- The POC gets a defendable answer for each LLM service type rather than a vague overall impression
- Prompt and model experiments become comparable because they run against the same frozen corpus
- The architecture's deterministic guardrails are still tested, but they no longer hide weak LLM behavior
- The testing burden stays bounded by using human review only where deterministic scoring is not credible
- Per-invocation metadata such as model ID, latency, token counts, confidence, and rationale becomes useful evaluation evidence rather than passive logging

### Negative

- The project must curate and maintain an evaluation corpus and scenario contracts in addition to normal tests
- Field Synthesis evaluation requires manual reviewer time
- Field Mapping evaluation also requires human effort to author and maintain canonical mappings
- A small frozen corpus is appropriate for a POC but can still miss failure modes that appear only under wider production variability
- Workflow Actions scoring becomes fragile if the canonical expected plans are underspecified or drift from the intended business scenarios

### Revisit Triggers

This decision should be revisited if:

- the four-service decomposition changes materially, making the scorecards no longer align with the service boundaries
- the POC introduces live MCP-based context retrieval, making frozen input capture significantly less representative
- human review burden becomes too large for Field Synthesis or plan adjudication, requiring a revised rubric or narrower scenario set
- production-like event volume or real learner data becomes available and the team needs a broader offline evaluation method than the initial representative corpus

## Open Questions

- *(Resolved 2026-07-04, see Decision §8.)*
- What exact rubric scale should Field Synthesis use: binary accept/reject, 3-point, or 5-point?
- Should Workflow Actions evaluation allow only one canonical plan per scenario, or should some scenarios explicitly define a small set of acceptable near-equivalent variants?
- What exact scenario count is the smallest set that still gives the team confidence across all supported event types and target combinations?
- Should the evaluation harness publish only pass/fail verdicts, or also preserve a structured failure taxonomy per service type for later fine-tuning work?
- How could a more automated LLM-as-a-judge component be added to this without creating too circular of outcomes?

## References

- [ADR 0001: Repository Structure](0001-repo-structure.md)
- [ADR 0007: LLM Decision Service Decomposition](0007-llm-decision-service-decomposition.md)
- [ADR 0008: Transformation Mapping Service Decomposition](0008-transformation-mapping-service-decomposition.md)
- [ADR 0009: Workflow Actions Orchestration Model](0009-workflow-actions-orchestration-model.md)
- [ADR 0011: Orchestration Runtime Technology](0011-orchestration-runtime-technology.md)
- [Skills Mobility Infrastructure POC Requirements](../2_requirements/poc-requirements.md)
