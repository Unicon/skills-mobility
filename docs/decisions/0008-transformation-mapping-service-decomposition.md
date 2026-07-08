# 0008. Transformation Mapping Service Decomposition

- Status: Accepted
- Date: 2026-06-15

> **Note (2026-06-25):** This ADR's two-loop pipeline and three-treatment field classification (direct mapping / synthesis placeholder / template pass-through) are the historical baseline. ADR-0017 introduces a third transformation phase and collapses field classification to two treatments (direct/synthesis). References to "two loops" and the three-treatment model in this ADR should be read accordingly.

## Context

The Transformation Mappings LLM Decision Service as described in ADR 0007 is responsible for generating the translation instructions that convert source data into the format expected by each selected delivery target. For this POC, the primary source inputs are:

- Mock LMS data representing a learner achievement event (course completion, skill mastery, badge award, etc.)
- Skills framework context from external sources such as O*NET

The primary delivery target being modeled is an Open Badges-compatible credential (representing the LearnCloud/LearnCard and SmartResume delivery path from an LMS).

The target schema for badge issuance in this POC is Open Badges 3.0, which is fixed and known in advance. The transformation task is not about determining the target schema structure — it is about generating the correct content to populate it.

Open Badges 3.0 fields fall into two distinct categories:

- **Credential-level fields** describe the achievement itself: what the badge represents, what criteria must be met, how the achievement aligns to skills frameworks such as O*NET, and any associated metadata. These fields are the same for every learner who earns the same credential from the same learning context. They represent the credential definition, not the individual learner's record.
- **Learner-level fields** describe the specific instance of the credential for a particular learner: who earned it, when, what evidence supports the claim, and any learner-specific narrative content.

On closer examination, populating these two categories follows the same three-phase pattern, applied twice in sequence:

**The pattern: field mapping → field synthesis → JSONata execution**

Within each pass, structural field mapping itself consists of three logical sub-steps:
- **Classify:** For each target field, decide whether it has a direct mapping from available source data or whether its value requires AI interpretation or synthesis.
- **Generate JSONata:** For each directly-mappable field, produce the JSONata expression that maps the source value to the target field.
- **Create placeholder markers:** For each field requiring synthesis, produce a structured input payload identifying the source data that should be synthesized, and a corresponding placeholder marker that (a) references that input payload and (b) is itself executable as a JSONata expression so that the generated value can be substituted into the final output by evaluating the expression.

**Loop 1 — Credential Template:** The first pass applies this pattern to the credential-level fields of the Open Badges 3.0 target schema, using LMS learning context data and skills framework knowledge as source inputs.
1. The Field Mapping LLM Decision Service produces a credential-level mapping specification: JSONata expressions for directly-mappable credential fields, and sourced placeholder markers for credential fields requiring synthesis.
2. The Field Synthesis LLM Decision Service generates values for the credential-level synthesis placeholders (for example, a summary course description given all the pages/modules of the course).
3. JSONata execution applies the expressions and substitutes the generated values, producing the credential template.

The credential template is independent of any individual learner and should be the same for every learner who earns this credential from this learning context. It is a natural candidate for storage and reuse across future events with the same context. Once stored, a future event can retrieve the credential template rather than running Loop 1 again.

**Loop 2 — Learner-Level Record:** The second pass applies the same pattern to the learner-level fields of the Open Badges 3.0 target schema, using the learner-specific LMS source data as the primary input and the credential template from Loop 1 as an additional input.
1. The Field Mapping LLM Decision Service produces a learner-level mapping specification: JSONata expressions for directly-mappable learner fields, and sourced placeholder markers for learner fields requiring synthesis.
2. The Field Synthesis LLM Decision Service generates values for the learner-level synthesis placeholders (for example, a summary of the assignment that validated the learner's skill mastery).
3. JSONata execution applies the expressions and substitutes the generated values, assembling the complete Open Badges 3.0 record.

This two-loop structure means the same Field Mapping and Field Synthesis pattern is applied twice by the same two services, with different source inputs and different target field sets each time. Loops 1 and 2 are sequential because Loop 2 requires the credential template produced by Loop 1 as an input.

This decomposition was also inspired by the DCC Credential Co-Writer project, which supports AI-assisted credential template design from learning content and skills framework knowledge. Running mock learning context data through the DCC Co-Writer (available at https://co-writer.dcconsortium.org/) is a viable way to prototype what the credential-level fields look like in practice. The entirety of Loop 1 in this ADR is a deliberate mock of the DCC Credential Co-Writer capability within the POC context.

The deterministic JSONata execution steps (phases 1c and 2c) are mocks of the LIF Translator, which was deferred in ADR 0004. The storage of AI-generated JSONata mapping specifications for reuse across future events is a mock of the LIF Metadata Repository (MDR), which was also deferred in ADR 0004. ADR 0004 explicitly anticipated this: "If AI-generated translation instructions become part of the design, an internal reimplementation of MDR-style storage is the natural place to manage them."

## Decision Drivers

- Recognize that credential-template population and learner-level record population follow the same reasoning pattern and should be structured symmetrically
- Produce the credential template as an explicit, inspectable, reusable artifact before any learner-specific mapping begins
- Separate structural mapping reasoning (which fields map where, and how) from generative synthesis reasoning (what should this interpreted field say)
- Within structural mapping, separate field classification (1-1 vs. synthesis) from JSONata generation and placeholder creation, at least conceptually
- Allow placeholder markers to carry their own source data specifications so the field synthesis step receives targeted briefs rather than raw full context
- Design placeholders to be executable as JSONata expressions so the same mechanism that marks synthesis fields can substitute generated values during final assembly
- Avoid proliferating services beyond what meaningfully improves quality or auditability

## Decision

The Transformation Mappings LLM Decision Service will be structured as a two-loop pipeline. Each loop applies the same three-phase pattern — field mapping, field synthesis, JSONata execution — to a different set of target fields and source inputs. The loops are sequential because the second loop depends on the credential template produced by the first.

Two LLM Decision Services implement this pipeline: the **Field Mapping LLM Decision Service** and the **Field Synthesis LLM Decision Service**. Each is invoked once per loop — twice in total across the full pipeline — with different inputs each time. There are no separate loop-specific service variants; the distinction between the credential-level and learner-level invocations is entirely in the inputs the orchestration layer provides.

### Loop 1 — Credential Template (Mock DCC Credential Co-Writer)

The entirety of Loop 1 — field mapping, field synthesis, and JSONata execution applied to credential-level fields — is a mock of the DCC Credential Co-Writer capability.

**Phase 1a — Field Mapping LLM Decision Service (Loop 1 invocation):** Given LMS learning context data (course content, learning objectives, assessment descriptions, etc.) and skills framework context (O*NET and others), produces a complete mapping specification for the credential-level fields of the Open Badges 3.0 target schema. The mapping specification assigns each credential-level field one of three treatments:

- A JSONata expression producing the value directly from the available source data
- A structured placeholder marker for fields whose values require interpretation or synthesis

Each placeholder marker identifies the target field and specifies which source data should be used to generate the value. The placeholder is also expressed in a form that can be evaluated as a JSONata expression during final assembly, so that the generated value can be substituted in place.

Within this service, the mapping task has three logical sub-steps: (1) classify each target field as directly mappable or requiring synthesis, (2) for directly-mappable fields, produce the JSONata expression, and (3) for synthesis fields, produce the input payload and placeholder marker. Whether these sub-steps are implemented as a single structured LLM output or as separate LLM invocations is an implementation decision discussed in the open questions below.

The resulting mapping specification — JSONata expressions and placeholder markers — should be stored for reuse, keyed by the source schema and target schema combination. This storage is a mock of the LIF Metadata Repository (MDR). Future events with the same source+target combination can retrieve the stored mapping specification and skip this phase, proceeding directly to field synthesis.

**Phase 1b — Field Synthesis LLM Decision Service (Loop 1 invocation):** Given the placeholder markers from phase 1a (each carrying its source data specification), generates the actual text values for each credential-level synthesis field — for example, a description of the achievement or its alignment rationale relative to a specific O*NET competency.

**Phase 1c — JSONata Execution (deterministic, Mock LIF Translator):** Executes the JSONata expressions from phase 1a against the available source data and substitutes the generated values from phase 1b for each placeholder, producing the credential template. This phase is a mock of the LIF Translator, which was deferred in ADR 0004.

The credential template is the achievement definition for this learning context, independent of any individual learner. It should be stored and reused for future events from the same context rather than regenerated each time.

### Loop 2 — Learner-Level Record

**Phase 2a — Field Mapping LLM Decision Service (Loop 2 invocation):** Given all relevant LMS source data for the specific learner event and the credential template from Loop 1 as an additional input, produces a complete mapping specification for the learner-level fields of the Open Badges 3.0 target schema. Each learner-level field receives one of three treatments:

- A JSONata expression producing the value directly from the LMS source data
- A JSONata pass-through expression pulling the value from the credential template
- A structured placeholder marker (with source data specification) for fields requiring interpretation or synthesis

As in phase 1a, the three logical sub-steps — classify, generate JSONata, create placeholders — may be implemented as a single structured LLM output or as separate invocations.

The resulting mapping specification should be stored in the mock MDR, keyed by source schema and target schema combination, so that future events with the same source+target pairing can retrieve it and skip this phase.

**Phase 2b — Field Synthesis LLM Decision Service (Loop 2 invocation):** Given the placeholder markers from phase 2a, generates the actual text values for each learner-level synthesis field — for example, a summary of the assignment that demonstrated the learner's skill mastery.

**Phase 2c — JSONata Execution (deterministic, Mock LIF Translator):** Executes the JSONata expressions from phase 2a against the source data and credential template, substitutes the generated values from phase 2b, and produces the complete Open Badges 3.0 record. As with phase 1c, this is a mock of the LIF Translator.

This ADR applies primarily to the Open Badges 3.0 delivery path. Whether other delivery targets follow the same two-loop pattern, require only Loop 2 (if a credential template already exists), or require a different pipeline shape is left to future design work.

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Single Transformation Mappings service (as described in ADR 0007) | One LLM call generates everything: credential template, JSONata mappings, enriched field values | Requires one prompt to carry skills framework knowledge, schema-mapping precision, and generative synthesis simultaneously; likely to produce lower-quality results across all three tasks |
| Single loop: treat credential-level and learner-level fields as one mapping pass | Skip the credential template as a distinct artifact; map all OBv3 fields in one pass per event | Loses the credential template as a reusable artifact; every event regenerates all fields including those that are the same across all earners; conflates context-specific reasoning with learner-specific reasoning |
| Two loops, field mapping and enrichment combined per loop | Each loop runs one LLM call that produces both JSONata and synthesized content | Coupling structural mapping and content synthesis in one prompt degrades the precision of the JSONata output; harder to test and audit each concern independently |
| Two loops, field mapping and enrichment separated per loop (chosen) | Each loop runs separate field mapping and field synthesis LLM invocations, followed by deterministic JSONata execution | Up to four LLM invocations for the transformation path (two field mapping, two field synthesis); sequential dependencies in each loop add latency |
| Two loops, field mapping further split into three separate LLM invocations per loop | Classify fields, then generate JSONata, then create placeholders as three separate LLM calls per loop | Up to six LLM invocations for transformation alone; overhead may not be justified if a single structured field mapping output handles all three sub-tasks reliably |

## Why This Structure

### The two-loop pattern reflects a genuine architectural boundary

Credential-level fields and learner-level fields are different in kind, not just in content. Credential-level fields describe the achievement for a learning context — they are stable, context-specific, and the same for every earner. Learner-level fields describe a specific instance of that achievement for a specific person. Separating these into two loops makes the credential template an explicit, inspectable, reusable artifact rather than an implicit intermediate result. A future event from the same learning context can retrieve the stored template and skip Loop 1 entirely.

### Two services are reused across both loops rather than having loop-specific variants

The Field Mapping LLM Decision Service and the Field Synthesis LLM Decision Service are each invoked twice — once per loop — rather than existing as separate credential-level and learner-level variants. The reasoning pattern is identical in both loops; only the inputs differ. The orchestration layer is responsible for providing the correct source data and target field set to each invocation. This keeps the service count low and avoids duplicating prompt engineering, testing, and maintenance work across what are fundamentally the same two operations applied to different data.

### Field Mapping and Field Synthesis must be separated within each loop

Field mapping is a precision task: the output must include machine-executable JSONata expressions. Errors break the pipeline. Introducing open-ended generative text synthesis into the same prompt degrades structural precision and makes the output harder to validate. Field synthesis is a generative task measured by coherence and relevance, not machine-executability. Coupling them produces worse results on both dimensions.

The placeholder mechanism is the design choice that makes this separation clean. Each placeholder marker carries its own source data specification, so the field synthesis step receives a targeted brief for each field rather than raw full context. Crucially, placeholders are also designed to be executable as JSONata expressions, so the same mechanism that marks a synthesis field during mapping can substitute the generated value during final assembly without requiring a separate structural pass.

### The three sub-steps of field mapping may or may not be separate LLM invocations

Within each field mapping phase, three logical things must happen: classify each target field as directly mappable or requiring synthesis, generate JSONata for the mappable fields, and produce placeholder markers (with source data payloads) for the synthesis fields. These sub-steps involve the same context and the same source-to-target reasoning, so a well-structured single LLM output may handle all three reliably. Splitting them into separate LLM invocations adds latency and cost without a clear quality benefit if the combined prompt remains focused. The POC should test whether a single field mapping invocation per loop produces acceptable results before considering further decomposition.

### POC value

The two-loop structure validates two meaningfully different AI capabilities within one workflow:

- **Loop 1 (credential-level)** demonstrates LLM-assisted credential design from learning content and skills framework knowledge — a direct analogue to the DCC Credential Co-Writer — including LLM-generated JSONata and field synthesis for credential description fields.
- **Loop 2 (learner-level)** demonstrates the same two services applied to learner-specific data, including LLM-generated narrative content such as assignment summaries that validate skill mastery.

Validating both loops in a single POC workflow increases the informational value of the POC significantly. The scope cost is real — up to four LLM invocations for the transformation path alone — but each invocation tests a distinct and independently valuable capability.

Additionally, capturing the output of the first loop could not only be heavily cached, but that loop could be it's own workflow to generate badge templates based on learning context as a value proposition on its own. By storing the credential template and field mappings for future use, this workflow can also be easily adapted into one with significantly more human review before these templates or mappings are used with actual learners.

## Sequencing and Pipeline Shape

The pipeline consists of two sequential loops. Within each loop, the three phases are also sequential. No phase can run until the preceding phase in the same loop has completed, and Loop 2 cannot begin until Loop 1 has completed.

```
LMS Learning Context Data + Skills Framework Context
        │
┌───── Loop 1: Credential Template (Mock DCC Credential Co-Writer) ──┐
│                                                                     │
│  [1a] Field Mapping LLM Decision Service (Loop 1)                   │
│       (classify fields → JSONata + placeholder markers)             │
│        ↓ Credential-level mapping spec  →  [store → Mock MDR]      │
│  [1b] Field Synthesis LLM Decision Service (Loop 1)                 │
│       (generate values for synthesis placeholders)                  │
│        ↓ Generated credential-level field values                    │
│  [1c] JSONata Execution (Mock LIF Translator)                       │
│        ↓ Credential Template  →  [store for reuse]                 │
└─────────────────────────────────────────────────────────────────────┘
        │
        ↓ Credential Template + Learner-Specific LMS Data
        │
┌───── Loop 2: Learner-Level Record ──────────────────────────────────┐
│                                                                     │
│  [2a] Field Mapping LLM Decision Service (Loop 2)                   │
│       (classify fields → JSONata + placeholder markers)             │
│        ↓ Learner-level mapping spec  →  [store → Mock MDR]         │
│  [2b] Field Synthesis LLM Decision Service (Loop 2)                 │
│       (generate values for synthesis placeholders)                  │
│        ↓ Generated learner-level field values                       │
│  [2c] JSONata Execution (Mock LIF Translator)                       │
│        ↓ Complete Open Badges 3.0 Record                            │
└─────────────────────────────────────────────────────────────────────┘
        │
Delivery Layer
```

If the credential template for a given learning context is already stored from a prior event, Loop 1 is skipped and the stored template is passed directly as input to Loop 2.

The Policy Rules Service may validate the credential template after phase 1c and the complete OBv3 record after phase 2c before delivery. The exact validation insertion points are left to the orchestration design.

## Consequences

### Positive

- The credential template is an explicit, inspectable, auditable artifact representing the achievement definition — independent of any individual learner and reusable across future events from the same learning context; once stored, Loop 1 is skipped for subsequent events
- AI-generated JSONata mapping specifications are stored in the mock MDR, keyed by source+target combination; future events with the same pairing can skip the field mapping LLM phase and proceed directly to field synthesis and JSONata execution
- The pipeline serves as a concrete mock of three deferred open source components: the DCC Credential Co-Writer (Loop 1), the LIF Translator (phases 1c and 2c), and the LIF MDR (mapping specification storage)
- Field mapping and field synthesis are separated within each loop, keeping each LLM invocation focused on a single kind of reasoning
- The placeholder mechanism creates a clean contract between field mapping and field synthesis: each placeholder carries its own source data specification, so the enrichment step receives targeted briefs rather than raw full context
- Placeholders double as JSONata expressions, so final assembly is a uniform JSONata execution pass with no structural special-casing for generated values
- Each phase can use a different model or configuration tuned to its task type
- The pipeline directly validates the ADR 0005 JSONata decision in a realistic end-to-end context

### Negative

- Up to four LLM invocations for the transformation path on a first-seen learning context (two Field Mapping invocations, two Field Synthesis invocations); this drops to two invocations (Loop 2 only) for events whose credential template is already stored
- The total per-event LLM call count across all services from ADR 0007 and this ADR is non-trivial and must be evaluated for acceptability during the POC
- Pipeline failures at any phase block all downstream phases; partial failure handling and retry logic must be designed explicitly
- Skills framework context (O*NET, etc.) must be available to the Loop 1 field mapping phase, which may require MCP integration or embedded context not yet designed
- The placeholder marker format must be precisely specified so it functions both as a source data brief and as an executable JSONata expression — this is a non-trivial implementation constraint

### Revisit Triggers

This decision should be revisited if:

- The placeholder mechanism proves too fragile in practice and inline content generation within the field mapping phase produces acceptable quality
- The credential templates for all relevant learning contexts prove stable enough to be pre-authored rather than LLM-generated, making Loop 1 unnecessary
- The sequential latency of two loops with multiple phases each proves unacceptable and a combined approach produces equivalent results
- Testing shows that combining the Field Mapping and Field Synthesis services into a single LLM invocation per loop does not degrade quality, making the per-loop separation unnecessary

## Open Questions

- Should the three logical sub-steps of each field mapping phase (classify, generate JSONata, create placeholders) be implemented as a single structured LLM output or as separate LLM invocations? A single invocation is simpler and lower-latency; separate invocations may improve classification quality by letting the LLM focus on one sub-task at a time. The POC should test the single-invocation approach first and split only if quality is insufficient.
- What is the structured format for placeholder markers? Each placeholder must identify the target field, specify the source data to use for synthesis (potentially multiple sources), and be expressible as a JSONata expression so it can be executed during final assembly. The exact schema for this contract between the Field Mapping and Field Synthesis services needs to be specified during implementation.
- What skills framework context does the credential-level field mapping phase need, and how is that context supplied — through MCP, embedded in the prompt, or retrieved from a dedicated knowledge source?
- How is credential template storage and retrieval keyed? The natural key is a learning context identifier (e.g. course ID or activity ID from the LMS), but the exact matching and invalidation logic — including what triggers regeneration of a stored template — is not yet defined.
- How are JSONata mapping specifications stored and retrieved in the mock MDR? The key should reflect the source schema and target schema combination, but what constitutes a distinct source+target pairing — and how schema changes invalidate stored mappings — needs to be defined. The mock MDR also needs to store placeholder markers alongside JSONata expressions, since both are needed to reconstruct the full mapping specification for the field synthesis phase.
- Is badge issuance and wallet delivery a single transformation path or two distinct paths with different target schemas? If the wallet delivery format differs from the OBv3 badge format, it may require its own two-loop pipeline or at minimum a different Loop 2.
- Does the SmartResume delivery target require the same two-loop pipeline, or does it have a simpler mapping path that does not require a credential template?

## References

- [ADR 0007: LLM Decision Service Decomposition](0007-llm-decision-service-decomposition.md)
- [ADR 0005: Schema Mapping Language](0005-schema-mapping-language.md)
- [ADR 0004: LIF Component Usage in the Initial POC](0004-lif-usage.md)
- [LIF Microservices Overview](https://github.com/LIF-Initiative/lif-core/blob/main/docs/overview/services-overview.md)
- [DCC Credential Co-Writer (Live Tool)](https://co-writer.dcconsortium.org/)
- [Skills Mobility Infrastructure POC Requirements](../2_requirements/poc-requirements.md)
- [O*NET Online](https://www.onetonline.org/)
