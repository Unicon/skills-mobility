# 0009. Workflow Actions Orchestration Model: Two-Stage Hierarchical Planning

- Status: Accepted
- Date: 2026-06-23
- Related: [ADR-0007](./0007-llm-decision-service-decomposition.md) · [ADR-0008](./0008-transformation-mapping-service-decomposition.md) · [ADR-0011](./0011-orchestration-runtime-technology.md)

## Context

ADR 0007 decomposed the monolithic LLM Decision Service into three specialized services: the Delivery Targets LLM Decision Service, the Transformation Mappings LLM Decision Service, and the Workflow Actions LLM Decision Service.

The key orchestration question is where Workflow Actions should sit relative to Delivery Targets and the downstream transformation and delivery steps. The main architectural pressures are:

- preserving the ability to terminate early before Delivery Targets when the event should not proceed at all, and
- allowing downstream planning to use the actual selected targets once Delivery Targets has run.

This becomes concrete when considering the range of events the POC must handle. Every event should not automatically trigger the full delivery path. Here are examples of cases that do not:

- A **skill mastered** event at a sub-competency level may not result in badge issuance. Some programs explicitly do not want credentials issued for sub-competencies — only for the parent competency. LMS systems like Canvas Learning Outcomes do not natively represent competency hierarchies; a flat outcome named "1.2.3" must be interpreted structurally by the Workflow Actions LLM to determine that it is a sub-competency not yet warranting delivery.
- A **course completed** event where the learner received a failing grade should not trigger delivery. The correct plan ends immediately without invoking Delivery Targets.
- A **badge awarded** event where the learner has not yet accepted the badge in the issuing system cannot be delivered downstream, since the badge is not retrievable from the API until accepted. The Workflow Actions service can add an acceptance-check step to the plan and abort the delivery path if acceptance has not occurred.

These cases show that the system needs a pre-delivery decision boundary that can stop the workflow before targets are selected. At the same time, steps such as LearnCard profile resolution, target-specific transformation seams, and target-specific delivery preparation are easier to plan correctly once the actual target set is known.

## Decision Drivers

- Preserve the ability to terminate before Delivery Targets when the event does not merit delivery
- Let the delivery-phase Workflow Actions invocation reason over the actual selected targets
- Keep Workflow Actions as a first-class orchestration decision boundary rather than collapsing downstream planning into fixed deterministic logic
- Keep the runtime model small enough for the POC
- Preserve deterministic validation and execution boundaries around LLM outputs

## Decision

The Workflow Actions LLM Decision Service will use a **two-stage hierarchical model**.

### Stage 1: Pre-target gate

The first Workflow Actions invocation runs **before** Delivery Targets.

Its job is to determine whether the workflow:

- terminates early with a named business outcome, or
- proceeds to Delivery Targets.

This first invocation is intentionally narrow. It is a gating decision, not the full delivery-phase plan.

### Stage 2: Delivery-phase planning

If the first invocation returns `continue`, the Orchestrator invokes the Delivery Targets LLM Decision Service.

The second Workflow Actions invocation then runs **after** Delivery Targets and receives:

- the event,
- the assembled context,
- the selected delivery targets,
- and the available service/action vocabulary.

This second invocation produces the abstract ordered plan for getting from the event and context to the selected target systems. The runtime then validates and executes that delivery-phase plan.

This is therefore a **two-call Workflow Actions model**, but not arbitrary mid-flight replanning. The second call occurs at one fixed orchestration boundary: after Delivery Targets, before execution of the delivery-phase plan.

Only the delivery-phase plan should be stored for reuse. The pre-target gate decision is execution-scoped and should run anew for each event.

## Resulting Invocation Order

The intended order is:

1. Event arrives.
2. Context Builder assembles source context.
3. Workflow Actions call 1 decides `terminate` or `continue`.
4. If `terminate`, the workflow ends.
5. If `continue`, Delivery Targets runs.
6. Workflow Actions call 2 generates the delivery-phase plan using the selected targets.
7. Policy Rules validates that delivery-phase plan when policy validation is active.
8. The Orchestrator executes the plan.

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Peer model | Delivery Targets and downstream transformation planning run before Workflow Actions planning | Cannot terminate cleanly before Delivery Targets; Workflow Actions becomes downstream coordination rather than the main planning boundary |
| Single-call hierarchical model | Workflow Actions runs once before Delivery Targets and emits the full plan | Target-specific downstream planning must happen without access to the actual selected targets |
| Two-stage hierarchical model (chosen) | Workflow Actions first decides terminate vs continue; Delivery Targets then runs; Workflow Actions runs again to produce the delivery-phase plan | Adds one extra Workflow Actions invocation and introduces two Workflow Actions artifacts instead of one |

## Why Two-Stage Hierarchical

### It preserves early termination

The first Workflow Actions call still allows the system to stop before Delivery Targets for cases such as:

- sub-competency events that should not issue a credential,
- failing course-completion events,
- or any future pre-delivery disqualifier that is visible from event or context alone.

### It gives the second planning call the target information it actually needs

Downstream steps such as LearnCard profile resolution, target-specific transformation seams, or wallet-delivery preparation are easier to plan correctly when the target set is already known. The two-stage model lets the second Workflow Actions call reason over real selected targets instead of hypothetical ones.

### It is still structurally constrained

This is not open-ended replanning after every step. The second planning boundary happens once, at a fixed place in the workflow. That keeps the runtime model simpler than a fully dynamic replanning system while addressing the main weakness of the single-call model.

### It keeps Workflow Actions meaningful as an orchestration decision boundary

The POC wants Workflow Actions to be more than a post-hoc delivery script generator. The two-stage model preserves that by keeping an early gating decision under Workflow Actions control while still allowing the later plan to use target-aware information.

## Implementation Implications

The two-stage hierarchical model has the following concrete implications for the orchestration engine design:

- **Two Workflow Actions contracts**: the Orchestrator needs a pre-target gate contract and a delivery-phase plan contract.
- **Invocation order**: Workflow Actions pre-target gate runs before Delivery Targets. Delivery Targets runs only on the continue path. The delivery-phase planning call runs after targets are selected.
- **Plan structure**: the second Workflow Actions call returns the abstract ordered plan the runtime executes. That plan names steps, bindings, and conditions rather than embedding target-system mechanics directly into the Orchestrator.
- **Plan validation**: when policy validation is active, the delivery-phase plan is validated before execution begins.
- **Artifact reuse**: only delivery-phase plans belong in the reusable-plan store. Pre-target gate decisions are recorded only as execution-scoped metadata and are not looked up for reuse. Delivery-phase plan applicability keys should include selected targets and whatever other planning dimensions the team decides are materially relevant.

## Consequences

### Positive

- Early termination remains possible before Delivery Targets
- Delivery-phase planning can use the actual selected targets
- LearnCard-specific and other target-specific steps no longer need to be planned blindly
- The model is still bounded enough for a POC executor

### Negative

- One additional Workflow Actions invocation on the continue path
- One execution-scoped pre-target gate decision to record plus one reusable delivery-phase plan artifact to persist and inspect
- More planner-path orchestration logic than the single-call model

### Revisit Triggers

This decision should be revisited if:

- the first Workflow Actions call rarely does anything beyond returning `continue`,
- the second Workflow Actions call still does not produce meaningfully target-aware plans,
- the extra LLM call materially harms latency without improving plan quality,
- or the project later needs arbitrary replanning after execution has already begun.

## Open Questions

- What is the minimum schema for the first Workflow Actions gate result?
- Which exact dimensions belong in the delivery-phase plan applicability key beyond event type and selected targets?
- What management surface should delete stored delivery-phase plans when the team wants to force regeneration?

## References

- [ADR-0007: LLM Decision Service Decomposition](./0007-llm-decision-service-decomposition.md)
- [ADR-0008: Transformation Mapping Service Decomposition](./0008-transformation-mapping-service-decomposition.md)
- [Skills Mobility Infrastructure POC Requirements](../2_requirements/poc-requirements.md)
