# 0007. LLM Decision Service Decomposition

- Status: Accepted
- Date: 2026-06-15

## Context

The POC requirements document defines a single **LLM Decision Service** with the following responsibilities:

- Determine delivery targets
- Determine transformation mappings
- Determine workflow actions
- Generate structured orchestration outputs
- Generate confidence scores
- Provide decision rationale

These three primary responsibilities — delivery target selection, transformation mapping generation, and workflow action determination — are grouped together in the requirements document as if they are naturally a single service. On closer examination, they are three distinct decision problems:

| Responsibility | What the LLM is doing | Key inputs | Key output |
| --- | --- | --- | --- |
| Delivery targets | Selecting which downstream systems should receive transformed data for this event | Event type, learner context, policy context, available delivery targets | Set of selected delivery targets with confidence and rationale |
| Transformation mappings | Generating the translation instructions that convert source data into a target system's expected format | Source schema, target schema(s), learner data, selected delivery targets | Transformation instructions (e.g. JSONata expressions) per delivery target |
| Workflow actions | Generating the complete orchestration plan specifying all steps the workflow should execute for this event | Event context, learner context, policy context, available actions, workflow state | Ordered execution plan covering all workflow steps, with conditions and rationale for each |

These are not just different outputs from the same reasoning task. They have different input requirements, different prompt strategies, different confidence profiles, and different failure modes. Transformation mappings, for example, require structural knowledge of source and target schemas that delivery target selection does not need. Workflow action planning requires understanding of available orchestration primitives and current workflow state that is irrelevant to the other two.

The POC requirements document also notes that the orchestration engine "could be a true orchestration engine or an AI agent with a goal of message delivery." This framing suggests the LLM is intended as the primary decision-maker for the workflow plan, not merely a source of supplementary hints. Under this interpretation, the Workflow Actions service does not just add steps on top of a pre-determined flow — it generates the complete orchestration plan that the execution engine then carries out, subject to validation by the deterministic Policy Rules Service.

## Decision Drivers

- Align each LLM invocation with a single, well-defined decision problem
- Allow prompt engineering to be scoped and optimized per decision type
- Support independent confidence thresholds and validation logic per decision type
- Enable independent testing and auditing of each decision in isolation
- Leave room to use different models or model configurations per service based on task complexity
- Preserve sequencing clarity by making inter-service dependencies explicit

## Decision

The LLM Decision Service described in the POC requirements will be decomposed into three distinct services:

1. **Delivery Targets LLM Decision Service** — determines which downstream delivery targets should receive transformed data for a given event.
2. **Workflow Actions LLM Decision Service** — generates the complete orchestration plan specifying all steps the workflow should execute for this event. The orchestration engine's role is to execute this plan faithfully, subject to validation by the deterministic Policy Rules Service.
3. **Transformation Mappings LLM Decision Service** — generates the transformation instructions (initially JSONata expressions, per ADR 0005) that convert source data into the structure expected by each selected delivery target.

These three services address distinct decision problems, but they are not fully independent. The Delivery Targets service must resolve before the Transformation Mappings service, because the correct mapping instructions depend on knowing which delivery targets have been selected. The relationship between the Workflow Actions service and the other two is an open architectural question discussed in the Sequencing and Dependencies section below.

This ADR does not decide whether the Transformation Mappings LLM Decision Service should itself be decomposed into further specialized services. That question is deferred to a follow-up ADR.

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Single monolithic LLM Decision Service | One service, one LLM call, returns all three decision outputs in a single structured response | Context window must carry all inputs for all three decisions; prompt must cover three genuinely different problems; harder to tune, test, or audit per decision type; one failure mode surfaces for all three outputs |
| Three specialized services (chosen) | Each decision type is handled by a dedicated service with its own prompt, inputs, output schema, and confidence logic | More LLM calls per workflow event; requires explicit sequencing of services with inter-service data dependencies |
| Two services: routing + transformation | Combine delivery targets and workflow actions into one routing service, keep transformation mappings separate | Routing and workflow action decisions are different enough in character that combining them does not simplify the prompt significantly; this option does not clearly improve on three services |

## Why Three Specialized Services

Each of the three decision types involves reasoning over a different slice of context with a different goal:

- **Delivery target selection** is primarily a routing and eligibility decision. It reasons over event type, learner state, and available targets to produce a small set of destinations. The prompt is relatively stable and the output schema is simple.
- **Transformation mapping generation** is a technical translation task. It requires detailed schema knowledge of both source and target and produces structured mapping instructions that need to be machine-executable. Prompt quality here is heavily dependent on how well the source and target schemas are presented, not on routing context.
- **Workflow action determination** is an orchestration planning task. Given the full event and learner context and the set of available orchestration primitives, it generates the complete plan of steps the workflow should execute. The orchestration engine acts as a faithful executor of that plan rather than as the primary decision-maker about what to do.

Keeping these in a single LLM call would require a single prompt to carry all three context sets and produce three structurally different outputs simultaneously. In practice, this tends to produce lower-quality results for each decision and makes it harder to iterate on any one of them without risking regressions in the others.

Splitting into three services also provides concrete benefits for testing and auditability. Each service can be evaluated independently, with its own fixtures, expected outputs, and confidence thresholds. The audit log can associate a confidence score and rationale with each specific decision type rather than a single blended score for all three.

The primary cost is additional LLM invocations per workflow event. For a POC whose goals include validating LLM decision quality and architecture, this is an acceptable and informative trade-off. The POC will help determine whether the per-invocation overhead is justified by the improvement in decision quality and maintainability.

## Sequencing and Dependencies

**Delivery Targets before Transformation Mappings** is a hard dependency. The mapping instructions must be tailored to each target system's expected structure, so the correct targets must be known before mappings can be generated.

**The relationship between Workflow Actions and the other two services is an open architectural question** with two plausible models:

- **Peer model:** All three services are invoked by the orchestration engine as independent upfront steps. The Workflow Actions service generates a complete plan that may reference the outputs of the Delivery Targets and Transformation Mappings services as data already in the execution context. In this model the three services are siblings, and the orchestration engine assembles their outputs into a coherent execution state.
- **Hierarchical model:** The Workflow Actions service is the top-level planner and its generated plan includes invocations of the Delivery Targets and Transformation Mappings services as named steps within the plan. Those services become sub-steps that the execution engine invokes on instruction rather than peers that run independently.

The peer model is simpler to implement and keeps the three services fully decoupled. The hierarchical model is more faithful to the LLM-as-orchestrator intent and allows the plan to conditionally include or skip the other two services based on event context. The choice between them has significant implications for how the orchestration engine is structured and is left to the orchestration design ADR.

In both models, the Policy Rules Service validates the complete plan before execution, providing the deterministic safety layer that does not depend on LLM reasoning.

## Consequences

### Positive

- Each service has a clear, bounded decision problem with a focused prompt and output schema
- Confidence scores, rationale, and audit records are attributed per decision type
- Services can be tuned, tested, replaced, or scaled independently
- Different models or configurations can be used per service based on task complexity and cost requirements
- Prompt engineering iteration on one service does not risk unintended changes to the others

### Negative

- At least two sequenced LLM invocations per workflow event before transformation can begin, with latency implications
- The orchestration layer must pass inter-service outputs as inputs, increasing data flow complexity
- More services to deploy, monitor, and maintain

### Revisit Triggers

This decision should be revisited if:

- The overhead of multiple LLM calls per event proves unacceptable in practice and a combined approach produces equivalent decision quality
- The three decision types prove to share enough context that a single structured prompt handles them reliably without quality loss
- The sequencing constraint between Delivery Targets and Transformation Mappings introduces unacceptable latency that cannot be addressed through parallelism

## Open Questions

- Should the Workflow Actions service and the other two services be structured as peers (all invoked independently by the orchestration engine) or hierarchically (Workflow Actions generates a plan that includes invoking the other two as named steps)? This choice significantly affects the orchestration engine design and should be addressed in the orchestration ADR.
- Should the Transformation Mappings LLM Decision Service itself be decomposed into further specialized services — for example, separating badge template generation, structural field mapping, and AI-generated content enrichment? This is the subject of a follow-up ADR.
- What model or configuration is appropriate for each of the three services? Should the Transformation Mappings service use a more capable model than the others given the structural precision required?
- How should inter-service failures be handled? If Delivery Targets fails or returns low-confidence results, should Transformation Mappings be blocked or should it proceed with a fallback set of targets?
- Should all three services be invoked for every event, or should some be conditionally invoked based on event type or policy context?

## References

- [ADR 0004: LIF Component Usage in the Initial POC](0004-lif-usage.md)
- [ADR 0005: Schema Mapping Language](0005-schema-mapping-langauge.md)
- [Skills Mobility Infrastructure POC Requirements](../2_requirements/poc-requirements.md)
