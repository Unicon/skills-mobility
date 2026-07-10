from typing import Any

from field_mapping.contracts import MappingRequest
from field_mapping.prompt_builder import (
    PROMPT_TEMPLATE_VERSION,
    build_user_message,
    system_prompt,
)


def _request() -> MappingRequest:
    return MappingRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="issuer_payload",
        source_system="mock_lms",
        fetch_profile_id="skill_mastered.v1",
        delivery_target="learncard_issuer",
        synthesis_allowed=True,
        source_payloads={"outcome": {"display_name": "Demonstrate the sample competency"}},
    )


def test_system_prompt_loads_versioned_template() -> None:
    prompt = system_prompt()
    assert "emit_mapping" in prompt
    assert "synthesis_allowed" in prompt  # the §6 rule is stated
    assert PROMPT_TEMPLATE_VERSION == "field_mapping.v1"


def test_user_message_includes_task_target_and_payloads() -> None:
    target: dict[str, Any] = {"x-transformation-type": "issuer_payload", "required": ["@context"]}
    message = build_user_message(_request(), target)
    assert "issuer_payload" in message
    assert "Target schema" in message
    assert "Source payloads" in message
    assert "display_name" in message  # the actual payload data is included
