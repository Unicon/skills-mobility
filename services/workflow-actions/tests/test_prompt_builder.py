from workflow_actions.contracts import GateRequest, PlanRequest
from workflow_actions.prompt_builder import (
    GATE_PROMPT_VERSION,
    PLAN_PROMPT_VERSION,
    build_gate_user_message,
    build_plan_user_message,
    gate_system_prompt,
    plan_system_prompt,
)


def _gate_request() -> GateRequest:
    return GateRequest(
        execution_id="exec_1",
        event_id="evt_1",
        event_type="skill_mastered",
        event={"learner_id": "learner_42"},
        context_bundle={"learner_id_value": "smi-demo-learner"},
    )


def _plan_request() -> PlanRequest:
    return PlanRequest(
        execution_id="exec_1",
        event_id="evt_1",
        event_type="skill_mastered",
        source_system="mock_lms",
        event={"learner_id": "learner_42"},
        context_bundle={"learner_id_value": "smi-demo-learner"},
        selected_targets=["learncard_issuer", "learncard_wallet"],
    )


def _registry_view() -> list[dict[str, str]]:
    return [{"action_id": "resolve_learncard_profile", "description": "Resolves profile."}]


def test_gate_prompt_version_constant() -> None:
    assert GATE_PROMPT_VERSION == "pre_target_gate.v1"


def test_plan_prompt_version_constant() -> None:
    assert PLAN_PROMPT_VERSION == "delivery_phase_plan.v1"


def test_gate_system_prompt_loads_template_and_injects_prose() -> None:
    prose = "Terminate on failing grades."
    prompt = gate_system_prompt(prose)
    assert "Terminate on failing grades." in prompt
    assert "emit_gate_decision" in prompt


def test_gate_user_message_includes_event_and_context() -> None:
    msg = build_gate_user_message(_gate_request())
    assert "skill_mastered" in msg
    assert "learner_42" in msg
    assert "smi-demo-learner" in msg


def test_gate_user_message_with_policy_context() -> None:
    req = _gate_request().model_copy(update={"policy_context": {"flag": "test"}})
    msg = build_gate_user_message(req)
    assert "Policy context" in msg
    assert "test" in msg


def test_plan_system_prompt_injects_registry() -> None:
    prompt = plan_system_prompt(_registry_view())
    assert "resolve_learncard_profile" in prompt
    assert "Resolves profile." in prompt


def test_plan_user_message_includes_targets_event_context() -> None:
    msg = build_plan_user_message(_plan_request())
    assert "learncard_issuer" in msg
    assert "learncard_wallet" in msg
    assert "skill_mastered" in msg
    assert "mock_lms" in msg
    assert "learner_42" in msg
