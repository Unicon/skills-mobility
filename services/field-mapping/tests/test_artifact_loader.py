from typing import Any

import pytest
from field_mapping.artifact_loader import MissingSourcePayloadError, load_source_payloads
from field_mapping.contracts import MappingRequest

_REQUIRED = ["outcome", "assignment", "module_context", "canvas_user", "submission"]


def _req(payloads: dict[str, Any]) -> MappingRequest:
    return MappingRequest(
        execution_id="exec_1",
        event_id="evt_1",
        transformation_type="issuer_payload",
        source_system="mock_lms",
        fetch_profile_id="skill_mastered.v1",
        delivery_target="learncard_issuer",
        synthesis_allowed=True,
        source_payloads=payloads,
    )


def test_loader_accepts_inline_payloads() -> None:
    # rubric is omitted (conditional) — that is allowed.
    req = _req({a: {} for a in _REQUIRED})
    assert load_source_payloads(req, required_aliases=_REQUIRED) == req.source_payloads


def test_loader_flags_missing_required_payload_alias() -> None:
    req = _req({"outcome": {}, "assignment": {}})  # missing three required aliases
    with pytest.raises(MissingSourcePayloadError) as exc:
        load_source_payloads(req, required_aliases=_REQUIRED)
    assert {"module_context", "canvas_user", "submission"} <= set(exc.value.missing)
