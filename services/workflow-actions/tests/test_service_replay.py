"""End-to-end tests for both stages in replay mode (design §13 step 4)."""

from typing import Any

from workflow_actions.contracts import (
    GateGeneration,
    GateRequest,
    LlmCallMeta,
    PlanApplicability,
    PlanGeneration,
    PlanRequest,
    PlanStep,
)
from workflow_actions.plan_store import PlanStore

from .conftest import SKILL_MASTERED_PLAN_BODY

_REPLAY_META = LlmCallMeta(provider="replay", model_id="replay", temperature=0.0)


class _CountingAdapter:
    """Wraps an adapter and counts method calls."""

    def __init__(
        self,
        inner: Any = None,
        fixed_gate: GateGeneration | None = None,
        fixed_plan: PlanGeneration | None = None,
    ) -> None:
        self.inner = inner
        self.fixed_gate = fixed_gate
        self.fixed_plan = fixed_plan
        self.gate_calls = 0
        self.plan_calls = 0

    def gate(
        self, request: GateRequest, *, gating_prose: str
    ) -> tuple[GateGeneration, LlmCallMeta]:
        self.gate_calls += 1
        if self.fixed_gate is not None:
            return self.fixed_gate, _REPLAY_META
        return self.inner.gate(request, gating_prose=gating_prose)

    def plan(
        self, request: PlanRequest, *, registry_view: list[dict[str, str]]
    ) -> tuple[PlanGeneration, LlmCallMeta]:
        self.plan_calls += 1
        if self.fixed_plan is not None:
            return self.fixed_plan, _REPLAY_META
        return self.inner.plan(request, registry_view=registry_view)


# ---------------------------------------------------------------------------
# Stage 1 — pre-target gate
# ---------------------------------------------------------------------------


def test_gate_skill_mastered_returns_continue(
    make_service: Any,
    skill_mastered_gate_request: GateRequest,
) -> None:
    resp = make_service().run_gate(skill_mastered_gate_request)
    assert resp.status == "succeeded"
    assert resp.decision == "continue"
    assert resp.confidence is not None and 0.0 <= resp.confidence <= 1.0
    assert resp.rationale
    assert resp.llm_invocation_log_ref is not None


def test_gate_unsupported_event_type_returns_terminate(
    make_service: Any,
    plan_store: PlanStore,
) -> None:
    request = GateRequest(
        execution_id="exec_99",
        event_id="evt_99",
        event_type="unknown_event_xyz",
        event={},
        context_bundle={},
    )
    resp = make_service().run_gate(request)
    assert resp.status == "succeeded"
    assert resp.decision is not None
    assert resp.decision == "terminate"


def test_gate_invalid_generation_returns_failed(
    make_service: Any,
    skill_mastered_gate_request: GateRequest,
) -> None:
    bad = GateGeneration(decision="do_something_invalid", confidence=0.9, rationale="x")
    adapter = _CountingAdapter(fixed_gate=bad)
    resp = make_service(adapter=adapter).run_gate(skill_mastered_gate_request)
    assert resp.status == "failed"
    assert resp.decision is None


def test_gate_exactly_one_adapter_attempt(
    make_service: Any,
    skill_mastered_gate_request: GateRequest,
) -> None:
    bad = GateGeneration(decision="bogus", confidence=0.9, rationale="x")
    adapter = _CountingAdapter(fixed_gate=bad)
    make_service(adapter=adapter).run_gate(skill_mastered_gate_request)
    assert adapter.gate_calls == 1


def test_gate_invocation_log_stored(
    make_service: Any,
    plan_store: PlanStore,
    skill_mastered_gate_request: GateRequest,
) -> None:
    resp = make_service().run_gate(skill_mastered_gate_request)
    assert resp.llm_invocation_log_ref is not None
    # The log can be loaded back.
    log = plan_store._read(resp.llm_invocation_log_ref)
    assert log["stage"] == "pre_target_gate"
    assert log["execution_id"] == "exec_1"
    # ADR-0010 §60: model-call metadata + the prompt sent + structured output.
    for field in (
        "service", "phase", "event_id", "provider", "model_id", "temperature",
        "input_tokens", "output_tokens", "latency_ms", "system_prompt", "user_prompt",
        "decision", "rationale",
    ):
        assert field in log, f"missing invocation-log field: {field}"
    assert log["provider"] == "replay"
    assert log["system_prompt"]  # the input a live model would receive


# ---------------------------------------------------------------------------
# Stage 2 — delivery-phase plan
# ---------------------------------------------------------------------------


def test_plan_skill_mastered_dual_target_end_to_end(
    make_service: Any,
    plan_store: PlanStore,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    resp = make_service().generate_plan(skill_mastered_plan_request)
    assert resp.status == "succeeded"
    assert resp.plan is not None
    assert resp.plan_ref is not None
    assert resp.confidence is not None and 0.0 <= resp.confidence <= 1.0
    assert resp.rationale
    assert resp.llm_invocation_log_ref is not None
    # 8-step Phase-1 plan
    assert len(resp.plan.steps) == 8
    # Stored plan round-trips.
    loaded = plan_store.load_plan(resp.plan_ref)
    assert loaded.applicability.event_type == "skill_mastered"


def test_plan_includes_all_phase1_action_ids(
    make_service: Any,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    resp = make_service().generate_plan(skill_mastered_plan_request)
    assert resp.plan is not None
    action_ids = {s.action_id for s in resp.plan.steps}
    expected = {
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "generate_wallet_payload_mapping",
        "execute_wallet_payload_translation",
        "deliver_to_learncard_wallet",
    }
    assert action_ids == expected


def test_plan_smartresume_selection_issues_then_delivers_to_smartresume(
    make_service: Any,
) -> None:
    # Finance routing: issuance still runs (LearnCard is the only issuer); the
    # selection changes only the final delivery step — no wallet actions.
    body = dict(SKILL_MASTERED_PLAN_BODY)
    body["selected_targets"] = ["learncard_issuer", "smart_resume"]
    resp = make_service().generate_plan(PlanRequest(**body))
    assert resp.status == "succeeded"
    assert resp.plan is not None
    action_ids = [s.action_id for s in resp.plan.steps]
    assert action_ids == [
        "resolve_learncard_profile",
        "generate_issuer_payload_mapping",
        "generate_issuer_payload_synthesis",
        "execute_issuer_payload_translation",
        "issue_learncard_badge",
        "deliver_to_smartresume",
    ]


def test_plan_both_final_targets_delivers_to_wallet_and_smartresume(
    make_service: Any,
) -> None:
    body = dict(SKILL_MASTERED_PLAN_BODY)
    body["selected_targets"] = ["learncard_issuer", "learncard_wallet", "smart_resume"]
    resp = make_service().generate_plan(PlanRequest(**body))
    assert resp.status == "succeeded"
    assert resp.plan is not None
    action_ids = [s.action_id for s in resp.plan.steps]
    assert action_ids[-2:] == ["deliver_to_learncard_wallet", "deliver_to_smartresume"]
    assert "issue_learncard_badge" in action_ids


def test_plan_invalid_generation_stores_failed_artifact(
    make_service: Any,
    plan_store: PlanStore,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    bad_plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer", "learncard_wallet"],
        ),
        steps=[
            PlanStep(
                step_id=1,
                action_id="invented_action_xyz",  # not in registry
                produces="out",
            )
        ],
        confidence=0.9,
        rationale="bad",
    )
    adapter = _CountingAdapter(fixed_plan=bad_plan)
    resp = make_service(adapter=adapter).generate_plan(skill_mastered_plan_request)
    assert resp.status == "failed"
    assert resp.plan is None
    assert resp.plan_ref is None


def test_plan_exactly_one_adapter_attempt(
    make_service: Any,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    bad_plan = PlanGeneration(
        applicability=PlanApplicability(
            event_type="skill_mastered",
            source_system="mock_lms",
            selected_targets=["learncard_issuer"],
        ),
        steps=[PlanStep(step_id=1, action_id="bogus_action", produces="out")],
        confidence=0.9,
        rationale="x",
    )
    adapter = _CountingAdapter(fixed_plan=bad_plan)
    make_service(adapter=adapter).generate_plan(skill_mastered_plan_request)
    assert adapter.plan_calls == 1


def test_plan_invocation_log_stored(
    make_service: Any,
    plan_store: PlanStore,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    resp = make_service().generate_plan(skill_mastered_plan_request)
    assert resp.llm_invocation_log_ref is not None
    log = plan_store._read(resp.llm_invocation_log_ref)
    assert log["stage"] == "delivery_phase_plan"
    assert log["execution_id"] == "exec_1"
    # ADR-0010 §60: model-call metadata + the prompt sent + structured output.
    for field in (
        "service", "phase", "event_id", "provider", "model_id", "temperature",
        "input_tokens", "output_tokens", "latency_ms", "system_prompt", "user_prompt",
        "confidence", "rationale",
    ):
        assert field in log, f"missing invocation-log field: {field}"
    assert log["provider"] == "replay"
    assert log["system_prompt"]  # the input a live model would receive


def test_plan_generator_metadata_set_correctly(
    make_service: Any,
    skill_mastered_plan_request: PlanRequest,
) -> None:
    resp = make_service().generate_plan(skill_mastered_plan_request)
    assert resp.plan is not None
    assert resp.plan.generator.service_version == "workflow-actions.v1"
    assert resp.plan.plan_schema_version == "v1"
    assert resp.plan.generated_at != ""
