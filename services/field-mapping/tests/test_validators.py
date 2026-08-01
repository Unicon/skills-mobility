from typing import Any

from field_mapping import validators
from field_mapping.contracts import MappingGeneration, MappingRequest, SynthesisRequestEntry
from field_mapping.validators import _top_level_object_keys, validate_generation

_TARGET: dict[str, Any] = {
    "x-transformation-type": "issuer_payload",
    "required": ["@context", "type", "issuer", "credentialSubject"],
}

# A well-formed issuer_payload mapping: all required top-level keys, a real source ref.
_VALID_JSONATA = (
    '{ "@context": ["x"], "type": ["y"], "issuer": {"id": "did"}, '
    '"credentialSubject": {"id": source_payloads.outcome.display_name} }'
)


def _request(**overrides: Any) -> MappingRequest:
    data: dict[str, Any] = {
        "execution_id": "exec_1",
        "event_id": "evt_1",
        "transformation_type": "issuer_payload",
        "source_system": "mock_lms",
        "fetch_profile_id": "skill_mastered.v1",
        "delivery_target": "learncard_issuer",
        "synthesis_allowed": True,
        "source_payloads": {"outcome": {"display_name": "X", "description": "Y"}},
    }
    data.update(overrides)
    return MappingRequest(**data)


def _gen(**overrides: Any) -> MappingGeneration:
    data: dict[str, Any] = {
        "jsonata": _VALID_JSONATA,
        "placeholder_ids": [],
        "synthesis_requests": [],
        "confidence": 0.9,
        "rationale": "direct maps only",
    }
    data.update(overrides)
    return MappingGeneration(**data)


def test_valid_jsonata_passes_without_execution() -> None:
    assert validate_generation(_gen(), request=_request(), target_schema=_TARGET) == []


def test_parse_gate_rejects_invalid_jsonata() -> None:
    errors = validate_generation(
        _gen(jsonata='{ "@context": '), request=_request(), target_schema=_TARGET
    )
    assert any("parse" in e for e in errors)


def test_placeholder_without_synthesis_request_fails() -> None:
    errors = validate_generation(
        _gen(placeholder_ids=["achievement_description"]), request=_request(), target_schema=_TARGET
    )
    assert any("no synthesis request" in e for e in errors)


def test_orphan_synthesis_request_fails() -> None:
    entry = SynthesisRequestEntry(
        placeholder_id="achievement_description",
        target_path="achievement.description",
        source_payloads={"outcome": {}},
        instruction="x",
    )
    errors = validate_generation(
        _gen(synthesis_requests=[entry]), request=_request(), target_schema=_TARGET
    )
    assert any("no matching placeholder" in e for e in errors)


def test_unknown_source_path_fails() -> None:
    bad = (
        '{ "@context": ["x"], "type": ["y"], "issuer": {"id": "d"}, '
        '"credentialSubject": {"id": source_payloads.nonexistent.field} }'
    )
    errors = validate_generation(_gen(jsonata=bad), request=_request(), target_schema=_TARGET)
    assert any("unknown source" in e for e in errors)


def test_output_keys_must_satisfy_target_required_fields() -> None:
    missing_issuer = '{ "@context": ["x"], "type": ["y"], "credentialSubject": {"id": "d"} }'
    errors = validate_generation(
        _gen(jsonata=missing_issuer), request=_request(), target_schema=_TARGET
    )
    assert any("issuer" in e for e in errors)


def test_synthesis_forbidden_rejects_any_placeholder() -> None:
    entry = SynthesisRequestEntry(
        placeholder_id="achievement_description",
        target_path="achievement.description",
        source_payloads={"outcome": {}},
        instruction="x",
    )
    errors = validate_generation(
        _gen(placeholder_ids=["achievement_description"], synthesis_requests=[entry]),
        request=_request(synthesis_allowed=False),
        target_schema=_TARGET,
    )
    assert any("synthesis_allowed is false" in e for e in errors)


def test_missing_confidence_or_rationale_fails() -> None:
    errors = validate_generation(
        _gen(confidence=None, rationale=None), request=_request(), target_schema=_TARGET
    )
    assert any("confidence" in e for e in errors)
    assert any("rationale" in e for e in errors)


# --- Direct unit tests for _top_level_object_keys ---


def test_nested_object_inside_array_inner_keys_not_counted() -> None:
    # An array of objects: inner keys ("inner_key") must NOT appear as top-level keys.
    expr = '{ "outer": [{ "inner_key": "v" }] }'
    keys = _top_level_object_keys(expr)
    assert "outer" in keys
    assert "inner_key" not in keys


def test_top_level_key_with_escaped_quote_in_value_is_found() -> None:
    # A top-level key whose string VALUE contains an escaped quote; key must be found.
    expr = '{ "title": "say \\"hello\\"" }'
    keys = _top_level_object_keys(expr)
    assert "title" in keys


def test_computed_key_not_counted_as_top_level() -> None:
    # Documented assumption: the LLM must emit literal field names. A required field
    # expressed as a computed key (e.g. ("a" & "b")) is NOT counted as top-level and
    # would be reported missing by the target-required-fields gate.
    expr = '{ ("a" & "b"): "value", "real_key": "v" }'
    keys = _top_level_object_keys(expr)
    assert "real_key" in keys
    # The computed concatenation result "ab" is not extracted as a key — the parser
    # only captures quoted string literals that are immediately followed by `:`.
    assert "ab" not in keys


NESTED_SCHEMA = {
    "type": "object",
    "required": ["credentialSubject"],
    "properties": {
        "credentialSubject": {
            "type": "object",
            "properties": {
                "achievement": {
                    "$ref": "#/$defs/Achievement",
                },
            },
        },
    },
    "$defs": {
        "Achievement": {
            "type": "object",
            "required": ["name", "description"],
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "alignment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["targetName"],
                        "properties": {"targetName": {"type": "string"}},
                    },
                },
            },
        },
    },
}


def test_nested_required_flagged_when_parent_built_without_leaf():
    # #125 live failure shape: the mapping constructs `achievement` but omits its
    # required name/description — FM must fail this itself, not defer to the TE.
    expr = '{ "credentialSubject": { "achievement": { "id": "x" } } }'
    errors = []
    validators._check_target_required_fields(expr, NESTED_SCHEMA, errors)
    joined = " ".join(errors)
    assert "credentialSubject.achievement.name" in joined
    assert "credentialSubject.achievement.description" in joined


def test_nested_required_inside_omitted_optional_branch_passes():
    # `alignment` is optional; omitting it entirely must NOT flag its required
    # leaves (JSON Schema semantics — required binds only when the branch exists).
    expr = '{ "credentialSubject": { "achievement": { "name": "n", "description": "d" } } }'
    errors = []
    validators._check_target_required_fields(expr, NESTED_SCHEMA, errors)
    assert errors == []


def test_nested_required_in_array_items_flagged_when_built():
    expr = (
        '{ "credentialSubject": { "achievement": { "name": "n", "description": "d",'
        ' "alignment": [{ "targetUrl": "u" }] } } }'
    )
    errors = []
    validators._check_target_required_fields(expr, NESTED_SCHEMA, errors)
    assert any("alignment.targetName" in e for e in errors)


def test_quoted_reference_literals_flagged():
    # Live #160 aftermath: '"id": "synthesized.credential_id"' put the literal
    # text into the credential and the LearnCard signer rejected it.
    expr = '{ "id": "synthesized.credential_id", "name": source_payloads.outcome.display_name }'
    errors = []
    validators._check_quoted_reference_literals(expr, errors)
    assert errors and "synthesized.credential_id" in errors[0]


def test_raw_references_and_ordinary_strings_pass():
    expr = (
        '{ "id": synthesized.credential_id, "type": ["Achievement"],'
        ' "note": "a plain sentence." }'
    )
    errors = []
    validators._check_quoted_reference_literals(expr, errors)
    assert errors == []
