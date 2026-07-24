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

# The workflow-context keys the executor populates before the plan runs.
# Binding resolvability for "workflow" source paths is checked against these.
# Matches the context keys the orchestrator planner uses (planner.py _phase1_steps).
WORKFLOW_CONTEXT_KEYS: frozenset[str] = frozenset(
    [
        "learner_id_value",
        "delivery_config_ref",
        "bundle",
        "issuer_id",
    ]
)


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
    workflow_context_keys: frozenset[str] = WORKFLOW_CONTEXT_KEYS,
) -> list[str]:
    """Validate a plan generation (Layer-A hard gates, design §8).

    Checks:
      1. confidence and rationale present
      2. registry conformance: every step's (action_id, type) in registry
      3. binding resolvability:
         - "workflow" path in workflow_context_keys
         - "step" step_id points to an earlier step that produces a value

    Does NOT check required-step presence (Layer B, FR-WA-22).
    """
    errors: list[str] = []

    if not (0.0 <= plan_generation.confidence <= 1.0):
        errors.append(f"plan confidence {plan_generation.confidence} is out of range [0,1]")

    if not plan_generation.rationale.strip():
        errors.append("plan rationale is empty")

    # Build a map of step_id -> produces for dependency resolution.
    produces_by_step: dict[int, str | None] = {}
    for step in plan_generation.steps:
        produces_by_step[step.step_id] = step.produces

    for step in plan_generation.steps:
        pair = (step.action_id, step.type)
        if pair not in registry:
            errors.append(
                f"step {step.step_id}: (action_id='{step.action_id}', type='{step.type}') "
                f"not in action registry"
            )

        for binding_name, binding in step.inputs.items():
            if binding.source == "workflow":
                path = binding.path or ""
                if path not in workflow_context_keys:
                    errors.append(
                        f"step {step.step_id} input '{binding_name}': "
                        f"workflow path '{path}' not in workflow context contract"
                    )
            elif binding.source == "step":
                ref_id = binding.step_id
                if ref_id is None:
                    errors.append(
                        f"step {step.step_id} input '{binding_name}': "
                        f"step binding missing step_id"
                    )
                elif ref_id >= step.step_id:
                    errors.append(
                        f"step {step.step_id} input '{binding_name}': "
                        f"step_id {ref_id} does not refer to an earlier step"
                    )
                elif produces_by_step.get(ref_id) is None:
                    errors.append(
                        f"step {step.step_id} input '{binding_name}': "
                        f"step {ref_id} does not produce a value"
                    )

    return errors
