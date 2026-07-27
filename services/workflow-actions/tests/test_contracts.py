from workflow_actions.contracts import (
    DeliveryPhasePlan,
    GateResponse,
    InputBinding,
    PlanApplicability,
    PlanGenerator,
    PlanResponse,
)

_GATE_SEAM_KEYS = {"status", "decision", "confidence", "rationale", "llm_invocation_log_ref"}
_PLAN_SEAM_KEYS = {
    "status",
    "plan",
    "plan_ref",
    "confidence",
    "rationale",
    "llm_invocation_log_ref",
}


def test_gate_response_succeeded_has_exact_seam_keys() -> None:
    resp = GateResponse.succeeded(
        decision="continue",
        confidence=0.98,
        rationale="no disqualifier",
        llm_invocation_log_ref="llmcall:g-1",
    )
    assert set(resp.model_dump().keys()) == _GATE_SEAM_KEYS
    assert resp.status == "succeeded"
    assert resp.decision == "continue"


def test_gate_response_failed_nulls_fields() -> None:
    resp = GateResponse.failed(llm_invocation_log_ref="llmcall:g-2")
    assert resp.status == "failed"
    assert resp.decision is None
    assert resp.confidence is None
    assert resp.rationale is None


def test_gate_response_failed_no_log_ref() -> None:
    resp = GateResponse.failed()
    assert resp.llm_invocation_log_ref is None


def test_plan_response_succeeded_has_exact_seam_keys() -> None:
    plan = DeliveryPhasePlan(
        plan_id="skill_mastered.learncard.v1",
        generator=PlanGenerator(service_version="workflow-actions.v1"),
        applicability=PlanApplicability(
            event_type="skill_mastered", selected_targets=["learncard_issuer"]
        ),
    )
    resp = PlanResponse.succeeded(
        plan=plan,
        plan_ref="plan:skill_mastered.mock_lms.learncard_issuer",
        confidence=0.94,
        rationale="dual target",
        llm_invocation_log_ref="llmcall:p-1",
    )
    assert set(resp.model_dump().keys()) == _PLAN_SEAM_KEYS
    assert resp.status == "succeeded"
    assert resp.plan is not None


def test_plan_response_failed_nulls_fields() -> None:
    resp = PlanResponse.failed(llm_invocation_log_ref="llmcall:p-2")
    assert resp.status == "failed"
    assert resp.plan is None
    assert resp.plan_ref is None


def test_input_binding_literal() -> None:
    b = InputBinding(source="literal", value="profile_id")
    assert b.source == "literal"
    assert b.value == "profile_id"
    assert b.path is None
    assert b.step_id is None


def test_input_binding_workflow() -> None:
    b = InputBinding(source="workflow", path="learner_id_value")
    assert b.source == "workflow"
    assert b.path == "learner_id_value"


def test_input_binding_step() -> None:
    b = InputBinding(source="step", step_id=1)
    assert b.source == "step"
    assert b.step_id == 1


