"""The real HTTP delivery-service clients — envelope POST shape + response handling."""

from __future__ import annotations

import json

import httpx
from orchestrator.clients import (
    EnvelopeContext,
    HttpContextBuilderClient,
    HttpDeliveryRouterClient,
    HttpProfileResolverClient,
)

_CTX = EnvelopeContext(
    workflow_id="exec_1",
    execution_id="exec_1",
    correlation_id="corr_1",
    delivery_config_ref="learncard-dev",
)


def _mock_client(handler, base_url):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url=base_url)


def test_http_context_builder_posts_and_returns_bundle():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "execution_id": "e1",
                "event_type": "skill_mastered",
                "source_data": {"outcome": {}},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://cb")
    cb = HttpContextBuilderClient("http://cb", client=client)
    bundle = cb.build_context("e1", {"metadata": {"event_name": "learning_outcome_result_created"}})

    assert captured["path"] == "/build-context"
    assert captured["body"] == {
        "execution_id": "e1",
        "event": {"metadata": {"event_name": "learning_outcome_result_created"}},
    }
    assert bundle["event_type"] == "skill_mastered"


def test_http_profile_resolver_posts_envelope_and_unwraps_result():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "result": {
                    "profile_id": "@learner",
                    "did": "did:web:x",
                    "resolution_method": "stored",
                },
                "error": None,
            },
        )

    resolver = HttpProfileResolverClient("http://pr", client=_mock_client(handler, "http://pr"))
    result = resolver.resolve("email", "learner@example.com", _CTX, "resolve_learncard_profile")

    assert captured["path"] == "/resolve-learncard-profile"
    assert captured["body"] == {
        "contract_version": "v1",
        "workflow_id": "exec_1",
        "execution_id": "exec_1",
        "step_id": "resolve_learncard_profile",
        "correlation_id": "corr_1",
        "delivery_config_ref": "learncard-dev",
        "payload": {"learner_id_type": "email", "learner_id_value": "learner@example.com"},
    }
    # On success the seam returns the inner result (what the executor threads on).
    assert result == {"profile_id": "@learner", "did": "did:web:x", "resolution_method": "stored"}


def test_http_profile_resolver_unresolved_becomes_failed_step():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "unresolved", "result": None, "error": None})

    resolver = HttpProfileResolverClient("http://pr", client=_mock_client(handler, "http://pr"))
    result = resolver.resolve("email", "nobody@example.com", _CTX, "resolve_learncard_profile")

    # A non-succeeded resolution surfaces as a failed step so the executor stops.
    assert result["status"] == "failed"


def test_http_delivery_router_posts_envelope_and_passes_response_through():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "status": "succeeded",
                "adapter_key": "learncard_issuer",
                "action": "issue_learncard_badge",
                "external_reference_id": "lc:issued:1",
                "result": {"issued_credential": {"proof": {}}},
                "error": None,
            },
        )

    router = HttpDeliveryRouterClient("http://dr", client=_mock_client(handler, "http://dr"))
    resp = router.dispatch(
        "issue_learncard_badge", {"unsigned_vc": {}}, _CTX, "issue_learncard_badge"
    )

    assert captured["path"] == "/delivery-actions"
    # adapter_key is derived from the action; the full envelope is forwarded.
    assert captured["body"]["action"] == "issue_learncard_badge"
    assert captured["body"]["adapter_key"] == "learncard_issuer"
    assert captured["body"]["contract_version"] == "v1"
    assert captured["body"]["execution_id"] == "exec_1"
    assert captured["body"]["payload"] == {"unsigned_vc": {}}
    # The normalized router response passes straight back to the executor/actions.
    assert resp["status"] == "succeeded"
    assert resp["result"]["issued_credential"] == {"proof": {}}
