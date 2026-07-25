"""Field Synthesis seam (#85): best-effort synthesis driven by the mapping's inline
synthesis request. No synthesis required, a failing service, or an absent inline
request all fall back to empty synthesized values (the obv3 stand-in still delivers)."""

from typing import Any

from orchestrator.actions import ActionDeps, _generate_field_synthesis
from orchestrator.clients import (
    EnvelopeContext,
    StubDeliveryRouter,
    StubFieldMapping,
    StubProfileResolver,
)

_ENV = EnvelopeContext(
    workflow_id="e1", execution_id="e1", correlation_id="c1", delivery_config_ref="cfg"
)

_REQUIRES_SYNTHESIS = {
    "requires_synthesis": True,
    "synthesis_request": {
        "synthesis_request_schema_version": "v1",
        "transformation_type": "issuer_payload",
        "requests": [
            {
                "placeholder_id": "achievement_description",
                "target_path": "achievement.description",
                "source_payloads": {"course": {"name": "Intro"}},
                "instruction": "Write it.",
            }
        ],
    },
}


class _SpyFieldSynthesis:
    def __init__(self, result: dict[str, Any] | None = None, raise_exc: bool = False) -> None:
        self.result = result
        self.raise_exc = raise_exc
        self.called = False

    def synthesize(
        self, transformation_type: str, synthesis_request: dict[str, Any], ctx: EnvelopeContext
    ) -> dict[str, Any]:
        self.called = True
        if self.raise_exc:
            raise RuntimeError("field synthesis unreachable")
        assert self.result is not None
        return self.result


def _deps(field_synthesis: Any) -> ActionDeps:
    return ActionDeps(
        profile_resolver=StubProfileResolver(),
        delivery_router=StubDeliveryRouter(),
        field_mapping=StubFieldMapping(),
        field_synthesis=field_synthesis,
        issuer_id="did:web:issuer",
        envelope=_ENV,
    )


def test_no_synthesis_required_skips_the_service() -> None:
    spy = _SpyFieldSynthesis()
    out = _generate_field_synthesis(
        {"mapping": {"requires_synthesis": False}, "transformation_type": "issuer_payload"},
        _deps(spy),
    )
    assert out == {"synthesized": {}}
    assert spy.called is False


def test_requires_synthesis_returns_service_values() -> None:
    spy = _SpyFieldSynthesis(
        result={"status": "succeeded", "values": {"achievement_description": "You did it."}}
    )
    out = _generate_field_synthesis(
        {"mapping": _REQUIRES_SYNTHESIS, "transformation_type": "issuer_payload"}, _deps(spy)
    )
    assert spy.called is True
    assert out == {"synthesized": {"achievement_description": "You did it."}}


def test_synthesis_failure_falls_back_to_empty() -> None:
    spy = _SpyFieldSynthesis(raise_exc=True)
    out = _generate_field_synthesis(
        {"mapping": _REQUIRES_SYNTHESIS, "transformation_type": "issuer_payload"}, _deps(spy)
    )
    assert spy.called is True
    assert out == {"synthesized": {}}


def test_requires_synthesis_but_no_inline_request_falls_back() -> None:
    spy = _SpyFieldSynthesis(result={"status": "succeeded", "values": {"x": "y"}})
    out = _generate_field_synthesis(
        {"mapping": {"requires_synthesis": True}, "transformation_type": "issuer_payload"},
        _deps(spy),
    )
    assert out == {"synthesized": {}}
    assert spy.called is False
