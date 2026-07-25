"""DynamoDB execution store, exercised against moto's in-process DynamoDB fake.

Mirrors the SQLite store's behavioral contract (test_store.py) and adds the
reason this backend exists: state written by one store instance is visible to a
separate instance reading the same table (the Lambda cross-invocation case).
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from orchestrator import planner
from orchestrator.schemas import DecisionArtifact, DecisionCandidate, StepResult
from orchestrator.store_dynamo import DynamoExecutionStore

TABLE = "orchestrator-executions-test"
REGION = "us-east-1"


@pytest.fixture
def dynamo(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoExecutionStore]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        boto3.resource("dynamodb", region_name=REGION).create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoExecutionStore(TABLE, region=REGION)


def test_list_executions_total_is_plan_step_count_not_attempted(
    dynamo: DynamoExecutionStore,
) -> None:
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer", "learncard_wallet"], "2026-01-01T00:00:00Z"
    )
    assert len(plan.steps) == 8  # guard: the Phase-1 plan is 8 steps

    dynamo.save_plan(plan, "skill_mastered|learncard_issuer,learncard_wallet")
    dynamo.create_execution("exec_fail", "evt", "corr", "skill_mastered")
    dynamo.set_plan("exec_fail", plan.plan_id)
    dynamo.set_status("exec_fail", "failed")
    dynamo.save_step(
        "exec_fail",
        StepResult(
            step_id=1,
            action_id="resolve_learncard_profile",
            status="failed",
            error={"message": "boom"},
        ),
    )

    (row,) = dynamo.list_executions()
    assert row.step_progress.completed == 0
    assert row.step_progress.total == 8  # from the plan, not the single attempted row


def test_list_executions_total_falls_back_when_no_plan(dynamo: DynamoExecutionStore) -> None:
    dynamo.create_execution("exec_gate", "evt", "corr", "unsupported")
    dynamo.set_status("exec_gate", "failed")

    (row,) = dynamo.list_executions()
    assert row.step_progress.completed == 0
    assert row.step_progress.total == 0


def test_list_executions_filters_by_correlation_id(dynamo: DynamoExecutionStore) -> None:
    dynamo.create_execution("exec_a", "evt", "corr_1", "skill_mastered")
    dynamo.create_execution("exec_b", "evt", "corr_2", "skill_mastered")

    rows = dynamo.list_executions(correlation_id="corr_1")
    assert [r.execution_id for r in rows] == ["exec_a"]


def test_record_decision_round_trips_gate_kind(dynamo: DynamoExecutionStore) -> None:
    dynamo.create_execution("exec_1", "evt", "corr", "skill_mastered")
    dynamo.record_decision(
        "exec_1",
        DecisionArtifact(
            kind="gate", confidence=1.0, rationale="ok", outcome="continue_to_delivery_targets"
        ),
    )
    meta = dynamo.get_execution_metadata("exec_1")
    assert meta is not None
    (decision,) = meta.decisions
    assert decision.kind == "gate"
    assert decision.confidence == 1.0
    assert decision.rationale == "ok"
    assert decision.outcome == "continue_to_delivery_targets"
    assert decision.candidates == []


def test_record_decision_preserves_insertion_order_and_candidates(
    dynamo: DynamoExecutionStore,
) -> None:
    dynamo.create_execution("exec_1", "evt", "corr", "skill_mastered")
    dynamo.record_decision(
        "exec_1", DecisionArtifact(kind="gate", outcome="continue_to_delivery_targets")
    )
    dynamo.record_decision(
        "exec_1",
        DecisionArtifact(
            kind="delivery_targets",
            outcome="learncard_wallet",
            candidates=[
                DecisionCandidate(label="learncard_wallet", confidence=0.9, selected=True),
                DecisionCandidate(label="smartresume", confidence=0.4, rationale="low fit"),
            ],
        ),
    )
    meta = dynamo.get_execution_metadata("exec_1")
    assert meta is not None
    assert [d.kind for d in meta.decisions] == ["gate", "delivery_targets"]
    candidates = meta.decisions[1].candidates
    assert candidates[0] == DecisionCandidate(
        label="learncard_wallet", confidence=0.9, selected=True
    )
    assert candidates[1] == DecisionCandidate(
        label="smartresume", confidence=0.4, rationale="low fit"
    )


def test_steps_are_sorted_and_upserted(dynamo: DynamoExecutionStore) -> None:
    dynamo.create_execution("exec_1", "evt", "corr", "skill_mastered")
    dynamo.save_step("exec_1", StepResult(step_id=2, action_id="b", status="succeeded"))
    dynamo.save_step("exec_1", StepResult(step_id=1, action_id="a", status="failed"))
    # a retry of step 1 overwrites, not appends
    dynamo.save_step("exec_1", StepResult(step_id=1, action_id="a", status="succeeded", attempt=2))

    meta = dynamo.get_execution_metadata("exec_1")
    assert meta is not None
    assert [(s.step_id, s.status, s.attempt) for s in meta.steps] == [
        (1, "succeeded", 2),
        (2, "succeeded", 1),
    ]


def test_plan_reuse_by_key_and_delete(dynamo: DynamoExecutionStore) -> None:
    plan = planner.delivery_phase_plan(
        "skill_mastered", ["learncard_issuer"], "2026-01-01T00:00:00Z"
    )
    key = "skill_mastered|learncard_issuer"
    dynamo.save_plan(plan, key)

    fetched = dynamo.get_plan_by_key(key)
    assert fetched is not None
    assert fetched.plan_id == plan.plan_id
    assert dynamo.get_plan_by_key("no-such-key") is None

    assert dynamo.delete_plan(plan.plan_id) is True
    assert dynamo.delete_plan(plan.plan_id) is False  # already gone
    assert dynamo.get_plan_by_key(key) is None


def test_state_persists_across_store_instances(dynamo: DynamoExecutionStore) -> None:
    # The whole reason for this backend: a second instance (a different Lambda
    # invocation) reading the same table sees state the first one wrote.
    dynamo.create_execution("exec_1", "evt", "corr", "skill_mastered")
    dynamo.record_decision(
        "exec_1", DecisionArtifact(kind="gate", outcome="continue_to_delivery_targets")
    )
    dynamo.set_result("exec_1", {"outcome": "delivered"})
    dynamo.set_status("exec_1", "completed")

    reader = DynamoExecutionStore(TABLE, region=REGION)
    meta = reader.get_execution_metadata("exec_1")
    assert meta is not None
    assert meta.status == "completed"
    assert meta.result == {"outcome": "delivered"}
    assert [d.kind for d in meta.decisions] == ["gate"]
