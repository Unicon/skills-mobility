# 0017. Three Transformation Phases for the Primary POC Transformation Path

- Status: Accepted
- Date: 2026-06-25

## Context

ADR-0008 established the main decomposition inside the transformation path:

- keep **Field Mapping** separate from **Field Synthesis**,
- preserve the **credential template** as an explicit reusable artifact,
- and use deterministic JSONata execution after LLM-produced mapping decisions.

That ADR also deliberately left one issue unresolved: whether badge issuance and wallet delivery should be treated as one transformation path or as distinct target-specific paths. Its final open questions note that if the wallet delivery format differs from the issued-badge format, the wallet path may require its own transformation path rather than being folded into the same learner-level pass.

The default expected POC path actually involves three distinct source-to-target transformations with three different target shapes:

1. generating the **credential template**
2. generating the **issuer payload** for badge issuance
3. generating the **wallet payload** after the badge has already been issued

Treating the second and third of those as one transformation obscures a real source/target boundary:

- before issuance, the system is transforming LMS-derived context plus the credential template into an issuer-facing payload
- after issuance, the system is transforming the **issued badge artifact** plus any delivery-specific context into a wallet-facing payload

That distinction matters for Field Mapping prompts, mapping-storage keys, orchestration step contracts, and evaluation of whether the LLM can do each job.

## Decision Drivers

- Define each transformation step by a concrete source data set and a concrete target schema
- Preserve the credential template as a first-class reusable artifact
- Keep the wallet transformation explicit rather than treating it as hidden adapter-side reshaping
- Allow mapping specifications to be stored and reused independently per transformation phase

## Decision

For the **default expected transformation path of the POC**, the transformation work will be treated as **three sequential transformation phases**.

"Phase" is used in this ADR as an architectural concept to describe the three distinct source-to-target transformation steps. In service request/response contracts, `transformation_type` is the preferred field name. The Workflow Actions LLM Decision Service is responsible for deciding which transformations occur and in what order, so the use of the word "phase" here is intended to denote a complete step with a default expected order but not a proscribed order.

### Phase 1 — `credential_template`

- **Primary sources:** LMS learning-context artifacts for the achievement definition
- **Optional supporting knowledge:** configured skills-framework grounding if the team chooses to use it
- **Target:** credential-template schema
- **Primary output artifact:** stored credential template

This phase is the POC analogue of AI-assisted credential-template design.

### Phase 2 — `issuer_payload`

- **Primary sources:** learner-specific LMS artifacts plus the stored credential template
- **Additional execution context:** any issuer-required execution data such as a resolved DID when that belongs in the target payload
- **Target:** issuer target schema / unsigned badge issuance payload
- **Primary output artifact:** issuer payload, which is then sent to the issuer adapter and results in an issued badge artifact

### Phase 3 — `wallet_payload`

- **Primary sources:** issued badge artifact plus any wallet-delivery-specific execution context
- **Target:** wallet target schema / wallet delivery payload
- **Primary output artifact:** wallet payload

If future delivery targets have their own post-issuance formats, they should be modeled as additional target-specific phases rather than hidden as incidental adapter behavior.

### Internal pattern within a phase

Each transformation phase may use the same internal pattern as needed:

1. **Field Mapping** — may be skipped when a stored mapping specification exists from a prior execution of the same source/target combination
2. **Field Synthesis** when the target schema contains fields that require synthesis
3. **Deterministic JSONata execution**

Field Synthesis is therefore **phase-specific, not universally mandatory**. The wallet payload phase may often be purely structural and skip synthesis entirely if the wallet target schema requires no synthesized fields.

### Mapping classifications

The Field Mapping service will classify fields only as:

- `direct`
- `synthesis`

This supersedes the three-classification model implied by ADR-0008 Phase 2a, which listed a credential-template pass-through as a distinct treatment alongside direct LMS-source mappings and synthesis placeholders. Under the three-phase model in this ADR, the credential template is a declared source artifact for Phase 2 rather than a special type of field classification. A mapping that pulls a value from the credential template is therefore `direct` — it maps directly from one of the declared source artifacts to a target field. The distinction ADR-0008 was capturing is now expressed by which source artifact a direct mapping draws from, not by a third classification.

`direct` means direct from one or more declared source artifact fields for the current phase. If a field in the issuer payload phase maps directly from the credential template, that is still `direct`. If a field in the wallet phase maps directly from the issued badge artifact, that is also `direct`.

### Artifact storage and reuse

- The credential template should be stored independently after Phase 1.
- Mapping artifacts should be stored independently per transformation phase and keyed by the relevant declared source-artifact shape plus target schema.
- The issued badge artifact becomes a first-class source artifact for the wallet payload phase. It is not stored for reuse: it contains learner PII, and the purpose of the pipeline is to deliver the credential to the wallet system — if the credential needs to be accessed again, the wallet system itself becomes the source rather than this pipeline's storage layer.

## Consequences

### Positive

- Each Field Mapping invocation now corresponds to one concrete source/target transformation problem
- Wallet-specific payload shaping becomes explicit and testable instead of being hidden in adapters or mislabeled as part of issuer preparation
- Stored mappings can be keyed more honestly by the actual source-artifact set and target schema of each phase
- The POC can evaluate credential-template generation, issuer-payload generation, and wallet-payload generation as distinct AI-assisted transformation jobs
- The classification model becomes simpler: only `direct` and `synthesis`

### Negative

- The default expected POC path now has up to three transformation phases instead of two
- A first-seen execution may require up to three Field Mapping invocations and, where relevant, up to three Field Synthesis invocations
- Several earlier documents describe the transformation path in two-loop terms and now need follow-up reconciliation; specifically, ADR-0010's per-service invocation count table (2× Field Mapping, 2× Field Synthesis) and ADR-0013's evaluation corpus scope ("both transformation loops defined in ADR 0008") both inherit the two-loop assumption from ADR-0008

## Relationship to Earlier ADRs

This ADR **refines ADR-0008** rather than replacing its whole rationale.

ADR-0008 remains valid in its key decisions to:

- separate Field Mapping from Field Synthesis,
- preserve the credential template as a reusable artifact,
- and use deterministic JSONata execution after the mapping and synthesis steps.

What this ADR changes is the **topology of the default expected POC transformation path**. The earlier two-loop framing is superseded for that default path by the three-phase model in this ADR.

This ADR also changes the invocation-count assumptions that earlier documents inherited from the two-loop framing. Those counts should now be interpreted as historical assumptions until the affected docs are updated.

## Open Questions

- When both LearnCard Wallet and SmartResume are active delivery targets, how are their target-specific delivery phases structured? Both will require a Phase 3 variant but with different target schemas. The open question is whether these run as parallel phases within one orchestration step or as sequential phases, and how the phases are keyed per delivery target — the three-phase model itself applies to both targets, but the orchestration topology for multiple simultaneous delivery phases is not yet defined.
- How much transformation is necessary between the issued badge and the target wallet system?
- Which fields, if any, in the wallet payload phase actually require Field Synthesis instead of direct structural mapping from the issued badge artifact?
- Should skills-framework grounding be provided through curated retrieval, static snapshots, or model priors alone for the credential-template phase?

## References

- [ADR-0005: Schema Mapping Language](./0005-schema-mapping-language.md)
- [ADR-0007: LLM Decision Service Decomposition](./0007-llm-decision-service-decomposition.md)
- [ADR-0008: Transformation Mapping Service Decomposition](./0008-transformation-mapping-service-decomposition.md)
- [ADR-0010: LLM Model Access Strategy](./0010-llm-model-access-strategy.md)
- [ADR-0013: LLM Decision Service Testing Approach](./0013-llm-decision-service-testing-approach.md)
