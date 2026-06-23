"""Ingress behavior: idempotency (business-key dedup), per-event-type identity,
rejection of malformed envelopes, capture-mode handoff, and reset."""

from __future__ import annotations

from event_consumer import consumer


def test_new_event_creates_execution_and_captures_handoff(store, skill_event):
    result = consumer.process(skill_event(), store)
    assert result.status == "created"
    assert result.execution_id and result.execution_id.startswith("exec_")
    # The initial execution record and the Orchestrator handoff are both inspectable.
    assert store.get_execution(result.execution_id)["status"] == "created"
    handoff = store.get_handoff(result.execution_id)
    assert handoff["envelope"]["metadata"]["event_id"] == "evt_1"


def test_redelivery_with_fresh_event_id_is_deduped(store, skill_event):
    first = consumer.process(skill_event(event_id="evt_1"), store)
    # Same business identity (event_name + user_id + outcome), different event_id.
    again = consumer.process(skill_event(event_id="evt_1_redelivered"), store)
    assert first.status == "created"
    assert again.status == "duplicate"
    assert again.execution_id == first.execution_id  # no new workflow created


def test_distinct_learner_is_a_new_workflow(store, skill_event):
    a = consumer.process(skill_event(user_id="U1"), store)
    b = consumer.process(skill_event(user_id="U2"), store)
    assert a.status == "created" and b.status == "created"
    assert a.execution_id != b.execution_id


def test_identity_keys_differ_per_event_type(store, skill_event, course_event, badge_event):
    # Each event type keys on its own object id; all three are distinct workflows.
    statuses = {
        consumer.process(skill_event(), store).status,
        consumer.process(course_event(), store).status,
        consumer.process(badge_event(), store).status,
    }
    assert statuses == {"created"}


def test_malformed_envelope_is_rejected(store, skill_event):
    bad = skill_event()
    del bad["metadata"]["user_id"]  # FR-EC-9 required field
    result = consumer.process(bad, store)
    assert result.status == "rejected"
    assert any("user_id" in e for e in result.errors)


def test_missing_event_type_object_id_is_rejected(store, skill_event):
    bad = skill_event()
    del bad["body"]["learning_outcome_id"]  # required for skill_mastered identity
    result = consumer.process(bad, store)
    assert result.status == "rejected"
    assert any("learning_outcome_id" in e for e in result.errors)


def test_reset_allows_demo_re_run(store, skill_event):
    first = consumer.process(skill_event(), store)
    assert first.status == "created"
    cleared = store.reset()
    assert cleared >= 1
    # After reset the same scenario produces a brand-new workflow (FR-EC-23).
    again = consumer.process(skill_event(), store)
    assert again.status == "created"
    assert again.execution_id != first.execution_id
