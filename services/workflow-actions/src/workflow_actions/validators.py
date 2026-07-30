"""Layer-A validation gates for gate decisions and delivery-phase plans (design §8).

Hard gates (ADR-0013 Layer A): structural validity alone is not success
(FR-WA-12/21/27). Each validator returns a list of error strings — empty = pass.

Layer B (required-step presence for a given applicability) is a test-harness
concern, NOT a hard gate here (FR-WA-22).
"""

from __future__ import annotations

from .contracts import GateGeneration, PlanGeneration

# The two valid gate decisions (FR-WA-2): exactly "continue" or "terminate".
# The reason for a terminate is carried in ``rationale``, not encoded in the
# decision string.
_VALID_DECISIONS = frozenset({"continue", "terminate"})

def validate_gate(
    generation: GateGeneration,
    *,
    allowed_decisions: set[str] | None = None,
) -> list[str]:
    """Validate a gate decision generation. Returns error list (empty = pass).

    allowed_decisions: explicit set of valid decisions; if None, the default
    rule applies (exactly "continue" or "terminate").
    """
    errors: list[str] = []
    decision = generation.decision

    if allowed_decisions is not None:
        if decision not in allowed_decisions:
            errors.append(
                f"gate decision '{decision}' is not in allowed set {sorted(allowed_decisions)}"
            )
    else:
        if decision not in _VALID_DECISIONS:
            errors.append(f"gate decision '{decision}' is not 'continue' or 'terminate'")

    if not (0.0 <= generation.confidence <= 1.0):
        errors.append(f"gate confidence {generation.confidence} is out of range [0,1]")

    if not generation.rationale.strip():
        errors.append("gate rationale is empty")

    return errors


def validate_plan(
    plan_generation: PlanGeneration,
    *,
    registry: set[tuple[str, str]],
) -> list[str]:
    """Validate a plan generation (Layer-A hard gates, design §8).

    Checks:
      1. confidence and rationale present
      2. registry conformance: every step's (action_id, type) in registry

    Binding resolvability is NOT checked here: since #112 the LLM emits ordered
    action_ids only (``plan_generation_from_llm_output`` always produces empty
    inputs), so there are no bindings to resolve — the orchestrator rebuilds
    them deterministically during re-binding (ADR-0022). Does NOT check
    required-step presence either (Layer B, FR-WA-22).
    """
    errors: list[str] = []

    if not (0.0 <= plan_generation.confidence <= 1.0):
        errors.append(f"plan confidence {plan_generation.confidence} is out of range [0,1]")

    if not plan_generation.rationale.strip():
        errors.append("plan rationale is empty")

    for step in plan_generation.steps:
        pair = (step.action_id, step.type)
        if pair not in registry:
            errors.append(
                f"step {step.step_id}: (action_id='{step.action_id}', type='{step.type}') "
                f"not in action registry"
            )

    return errors
