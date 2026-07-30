from field_synthesis.prompt_builder import (
    PROMPT_VERSION,
    build_user_message,
    system_prompt,
)

from .conftest import make_artifact, make_brief


def _request_with_artifact() -> tuple[object, list[object]]:
    from field_synthesis.contracts import SynthesisRequest

    briefs = [
        make_brief(
            "field_a", "some.field_a", "Describe A.", {"course": {"desc": "Data science intro."}}
        ),
        make_brief("field_b", "some.field_b", "Summarize B.", {"learner": {"name": "Alice"}}),
    ]
    artifact = make_artifact(briefs=briefs, transformation_type="issuer_payload")
    req = SynthesisRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="issuer_payload",
        synthesis_request=artifact,
    )
    return req, briefs


def test_system_prompt_loads_versioned_template() -> None:
    prompt = system_prompt()
    assert "emit_synthesis" in prompt
    assert PROMPT_VERSION == "field_synthesis.v1"


def test_user_message_includes_transformation_type_and_briefs() -> None:
    req, briefs = _request_with_artifact()
    message = build_user_message(req, briefs)  # type: ignore[arg-type]
    assert "issuer_payload" in message
    assert "field_a" in message
    assert "field_b" in message
    assert "Describe A." in message


def test_user_message_includes_source_payloads() -> None:
    req, briefs = _request_with_artifact()
    message = build_user_message(req, briefs)  # type: ignore[arg-type]
    assert "Data science intro." in message
    assert "Alice" in message
