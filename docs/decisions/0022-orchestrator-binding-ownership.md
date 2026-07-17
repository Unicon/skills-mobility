# 0022. Orchestrator Binding Ownership: Re-Binding Instead of Strict Plan Conformance

- Status: Proposed
- Date: 2026-07-16

## Context

ADR-0011 defined an executor that resolves each step's inputs solely from that step's declared
`InputBinding` entries. Bindings carry a source (`workflow`, `step`, or `literal`) and, for
`step`-source bindings, an explicit `step_id` integer pointing at the prior step whose output to
pass in.

When the Workflow Actions LLM Decision Service generates a delivery-phase plan (ADR-0009 stage 2),
it can reason about which actions to run and in what order, but it has no reliable way to emit
correct `step_id` values. Those integers are positional artifacts of the executor's own step-list
representation — implementation detail, not domain concept. The LLM reliably knows *which*
produced value it needs (e.g. "the resolved profile from the profile-resolution step"), but not
which integer that step landed on after the orchestrator assembled the plan.

The Phase-1 guardrail addressed this by strict plan conformance (`_plan_conforms`): the engine
compared the proposed plan step-for-step against the deterministic reference and fell back
whenever the plans diverged. This worked for Phase 1 because the deterministic stub was always
the only real plan, so the conformance check was always a no-op. But it made LLM-generated plans
inert in practice: any plan whose inputs differed from the reference — including plans whose
action selection or ordering was legitimately different — would fail conformance and be replaced
by the reference regardless of the LLM's intent. The LLM's action-selection reasoning was
recorded in the audit trail but never actually executed.

## Decision Drivers

- LLM-generated plans must be able to actually execute, not just be recorded, for the
  Workflow Actions seam to have any research value (ADR-0007, ADR-0013)
- The executor's `InputBinding` model must not change — it is the stable contract between the
  planner, the engine, and the executor (ADR-0011)
- LLM output must never flow straight to delivery without a deterministic guardrail (ADR-0007)
- The guardrail mechanism should let the LLM own action selection, ordering, and skip decisions,
  while the orchestrator owns the binding correctness that makes execution safe

## Decision

The engine replaces strict plan conformance with **orchestrator-owned re-binding**.

When the Workflow Actions service returns a proposed plan, the engine calls
`planner.rebind_plan(proposed, event_type)` instead of comparing it against the reference.
Re-binding:

1. Derives per-action binding templates from the deterministic planner. The full
   all-targets deterministic plan is built once and indexed by `action_id`. For each action the
   template records what each input needs: a workflow-context path, a literal value, or the
   *produced-name* of a prior step's output (not its integer step_id).

2. Walks the LLM's action sequence in order, assigning new sequential `step_id`s (1, 2, 3, …).
   For each step, inputs are built from the template: `step`-source bindings are resolved by
   looking up the produced-name in a `produced → step_id` map accumulated so far.

3. Returns the re-bound plan (same action sequence as the LLM chose, correct integer bindings)
   on success, or `None` if any action is unknown or any cross-step dependency is not yet
   satisfied at the point it is needed.

If re-binding succeeds, the re-bound plan executes. If it returns `None`, the engine logs a
warning and falls back to the deterministic reference plan — the same fallback as before.

**Ownership boundary:**

- The LLM owns action selection, ordering, and which steps to skip. If it emits a shorter plan
  (e.g. omitting wallet delivery for a SmartResume-only path), re-binding honors that.
- The orchestrator owns binding correctness and executability. Re-binding is the only place
  `step_id` integers are assigned to executor bindings; the LLM never sets them.

**What re-binding does not validate:**

Re-binding guarantees only that the plan is *executable* — its bindings are internally consistent
and every referenced dependency is satisfied in the order the LLM chose. It does not validate
whether the LLM's action selection is *semantically correct* for the event and targets. A
bindable-but-semantically-odd plan (e.g. a plan that skips a required delivery step) would still
execute. That correctness check is handled by:

- the pre-target gate (stage-1 Workflow Actions decision, ADR-0009),
- a future Policy Rules Service that will validate plans against domain rules before execution
  (ADR-0011 §1), and
- the deterministic fallback and complete audit trail, which together make a mis-sequenced plan
  visible and recoverable.

## Consequences

### Positive

- LLM-generated plans now actually execute; the Workflow Actions seam has real research value
- The executor and `InputBinding`/`PlanStep` schemas are unchanged — re-binding is purely a
  planner/engine concern
- The deterministic fallback is preserved for plans with unknown actions or unmet dependencies
- The LLM's flexibility to select, reorder, or skip steps is no longer blocked by the conformance
  check's require-all-steps-in-order constraint
- The produced-name indirection insulates the binding logic from the executor's integer step_ids,
  making it robust to future plan structure changes

### Negative

- Re-binding validates executability, not semantic correctness; a policy mistake in the LLM's
  action selection runs until the Policy Rules Service is in place
- The all-targets deterministic plan is built on every non-reused plan generation call to derive
  templates (one extra in-process function call, not a service round-trip)

### Supersedes

Strict plan conformance (`_plan_conforms` in `engine.py`) is removed. The function and all tests
for it are deleted. Re-binding subsumes its guardrail role with looser structural constraints and
stronger binding correctness.

### Revisit Triggers

- When the Policy Rules Service is implemented (ADR-0011): the binding check can be extended or
  replaced with policy-aware validation that covers semantic correctness, not just executability
- If the LLM begins emitting plans whose action sets diverge significantly from the deterministic
  catalog (new action_ids, novel orderings), add an allowlist or policy check at the template
  lookup boundary rather than tightening re-binding itself

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Re-binding with produced-name templates (chosen) | Orchestrator derives binding templates from the deterministic planner; LLM owns action sequence; orchestrator fills in correct step_id integers | Does not validate semantic correctness of action selection — mitigated by gate + future Policy Service + fallback |
| Strict conformance (`_plan_conforms`, removed) | Proposed plan must match the reference step-for-step with at least the required inputs; otherwise fall back | Made LLM plans inert — any deviation (even a semantically valid shorter plan) triggered the fallback, so the LLM's action selection never actually executed |
| Prompt the LLM to emit produced-names instead of step_ids | Change the Workflow Actions prompt so the LLM references prior steps by their produced-name rather than an integer | Requires a prompt contract change and a separate produced-name→step_id resolution pass at execution time; the orchestrator still has to own the mapping, so the binding-ownership concern is not resolved |
| Full schema validation only | Validate that the proposed plan is a well-formed `DeliveryPhasePlan` and execute it as-is | LLM-supplied step_id integers in bindings would be wrong; the executor would fail at runtime rather than at plan-acceptance time |

## References

- [ADR-0007: LLM Decision Service Decomposition](0007-llm-decision-service-decomposition.md)
- [ADR-0009: Workflow Actions Orchestration Model: Two-Stage Hierarchical Planning](0009-workflow-actions-orchestration-model.md)
- [ADR-0011: Orchestration Runtime Technology](0011-orchestration-runtime-technology.md)
- [ADR-0013: LLM Decision Service Testing Approach](0013-llm-decision-service-testing-approach.md)
