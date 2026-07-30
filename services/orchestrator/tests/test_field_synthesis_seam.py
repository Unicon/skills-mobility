"""Field Synthesis seam (#85): best-effort synthesis driven by the mapping's inline
synthesis request. No synthesis required, a failing service, or an absent inline
request all fall back to empty synthesized values (the obv3 stand-in still delivers)."""

from typing import Any

from orchestrator.actions import DEGRADED_KEY, ActionDeps, _generate_field_synthesis
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


def test_requires_synthesis_returns_service_values_and_preserves_envelope() -> None:
    spy = _SpyFieldSynthesis(
        result={
            "status": "succeeded",
            "values": {"achievement_description": "You did it."},
            "confidence": 0.87,
            "rationale": "grounded in the course description",
            "synthesis_result_ref": "synthesis_result:sk_1",
            "llm_invocation_log_ref": "llmcall:sk_1",
        }
    )
    out = _generate_field_synthesis(
        {"mapping": _REQUIRES_SYNTHESIS, "transformation_type": "issuer_payload"}, _deps(spy)
    )
    assert spy.called is True
    assert out["synthesized"] == {"achievement_description": "You did it."}
    # FR-FS-9 / design §12: confidence + rationale (and the artifact refs) must
    # survive into the step output so the execution record can recover them.
    assert out["confidence"] == 0.87
    assert out["rationale"] == "grounded in the course description"
    assert out["synthesis_result_ref"] == "synthesis_result:sk_1"
    assert out["llm_invocation_log_ref"] == "llmcall:sk_1"


def test_failed_status_response_falls_back_to_empty() -> None:
    # The service answered at the HTTP level but reported a failed synthesis —
    # a distinct branch from the call raising.
    spy = _SpyFieldSynthesis(
        result={"status": "failed", "values": None, "llm_invocation_log_ref": "llmcall:sk_2"}
    )
    out = _generate_field_synthesis(
        {"mapping": _REQUIRES_SYNTHESIS, "transformation_type": "issuer_payload"}, _deps(spy)
    )
    assert spy.called is True
    # #131: a real, attempted call that failed is audit-visible via the marker.
    assert out == {"synthesized": {}, DEGRADED_KEY: "field-synthesis returned failed"}


def test_synthesis_failure_falls_back_to_empty() -> None:
    spy = _SpyFieldSynthesis(raise_exc=True)
    out = _generate_field_synthesis(
        {"mapping": _REQUIRES_SYNTHESIS, "transformation_type": "issuer_payload"}, _deps(spy)
    )
    assert spy.called is True
    assert out["synthesized"] == {}
    assert out[DEGRADED_KEY].startswith("field-synthesis failed:")


def test_requires_synthesis_but_no_inline_request_falls_back() -> None:
    spy = _SpyFieldSynthesis(result={"status": "succeeded", "values": {"x": "y"}})
    out = _generate_field_synthesis(
        {"mapping": {"requires_synthesis": True}, "transformation_type": "issuer_payload"},
        _deps(spy),
    )
    assert out == {"synthesized": {}}  # no marker: nothing was attempted
    assert spy.called is False
