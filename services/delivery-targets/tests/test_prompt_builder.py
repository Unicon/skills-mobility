from typing import Any

from delivery_targets.contracts import SelectionRequest
from delivery_targets.prompt_builder import (
    PROMPT_TEMPLATE_VERSION,
    build_user_message,
    system_prompt,
)


def _request() -> SelectionRequest:
    return SelectionRequest(
        execution_id="exec_1",
        event_id="evt_1",
        event_type="skill_mastered",
        source_system="mock_lms",
        learner_context={"learner_id": "learner_42", "credential_enabled": True},
    )


def _catalog() -> list[dict[str, Any]]:
    return [
        {
            "delivery_target": "learncard_issuer",
            "delivery_action": "issue_learncard_badge",
            "description": "Issues a verifiable badge.",
            "eligibility_notes": "For credential-enabled courses.",
        }
    ]


def test_system_prompt_loads_versioned_template() -> None:
    prompt = system_prompt()
    assert "emit_selection" in prompt
    assert PROMPT_TEMPLATE_VERSION == "delivery_targets.v1"


def test_user_message_includes_event_catalog_and_context() -> None:
    message = build_user_message(_request(), _catalog())
    assert "skill_mastered" in message
    assert "learncard_issuer" in message
    assert "learner_42" in message
    assert "Available delivery targets" in message
    assert "Learner context" in message


def test_user_message_includes_source_system() -> None:
    message = build_user_message(_request(), _catalog())
    assert "mock_lms" in message
