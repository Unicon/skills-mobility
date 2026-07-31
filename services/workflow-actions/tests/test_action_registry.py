"""Tests for the action registry and action_registry_view module."""

from workflow_actions.action_registry_view import (
    gating_prose,
    prompt_projection,
    valid_action_pairs,
)

_EXPECTED_ACTION_IDS = {
    "resolve_learncard_profile",
    "generate_credential_template_mapping",
    "generate_credential_template_synthesis",
    "execute_credential_template_translation",
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "execute_issuer_payload_translation",
    "issue_learncard_badge",
    "generate_learncard_wallet_payload_mapping",
    "execute_learncard_wallet_payload_translation",
    "deliver_to_learncard_wallet",
    "generate_smartresume_payload_mapping",
    "execute_smartresume_payload_translation",
    "deliver_to_smartresume",
}


def test_valid_action_pairs_contains_all_phase1_actions() -> None:
    pairs = valid_action_pairs()
    action_ids = {action_id for action_id, _ in pairs}
    assert action_ids == _EXPECTED_ACTION_IDS


def test_prompt_projection_has_action_id_and_description() -> None:
    projection = prompt_projection()
    assert len(projection) == len(_EXPECTED_ACTION_IDS)
    for entry in projection:
        assert "action_id" in entry
        assert "description" in entry
        assert entry["action_id"] in _EXPECTED_ACTION_IDS
        assert len(entry["description"]) > 10  # non-trivial description


def test_gating_prose_is_non_empty_string() -> None:
    prose = gating_prose()
    assert isinstance(prose, str)
    assert len(prose) > 50
    # Should mention the core disqualifier types.
    assert "fail" in prose.lower() or "sub-competency" in prose.lower()
