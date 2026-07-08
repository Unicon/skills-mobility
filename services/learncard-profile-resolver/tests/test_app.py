"""API tests for the LearnCard Profile Resolver — no network, in-memory store."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi.testclient import TestClient
from learncard_api import LearnCardClient, LearnCardSettings
from learncard_profile_resolver.app import create_app
from learncard_profile_resolver.config import Settings

ENDPOINT = "/resolve-learncard-profile"
DID = "did:web:network.learncard.com:users:smi-learner-1"


def _app(handler: Callable[[httpx.Request], httpx.Response]) -> tuple[TestClient, object]:
    lc = LearnCardClient(
        LearnCardSettings(api_url="https://net.example/api", api_token="tok-123"),
        transport=httpx.MockTransport(handler),
    )
    app = create_app(Settings(db_path=":memory:"), lc)
    return TestClient(app), app.state.store


def _request(id_type: str, id_value: str) -> dict[str, object]:
    return {
        "contract_version": "v1",
        "workflow_id": "wf_1",
        "execution_id": "exec_1",
        "step_id": "step_resolve_profile",
        "correlation_id": "corr_1",
        "delivery_config_ref": "learncard-dev",
        "payload": {"learner_id_type": id_type, "learner_id_value": id_value},
    }


def _no_call(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"unexpected LearnCard call: {request.url}")


def test_stored_returns_without_api_call() -> None:
    # Assert the no-call invariant explicitly (a counted transport), not via an
    # uncaught AssertionError that a future broad except-handler could swallow.
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=[])

    tc, store = _app(handle)
    store.put("profile_id", "smi-learner-1", "smi-learner-1", DID, "searched")  # type: ignore[attr-defined]

    body = tc.post(ENDPOINT, json=_request("profile_id", "smi-learner-1")).json()

    assert body["status"] == "succeeded"
    assert body["result"] == {
        "profile_id": "smi-learner-1",
        "did": DID,
        "resolution_method": "stored",
    }
    assert len(calls) == 0  # stored hit short-circuits before any LearnCard search
    # Correlation ids preserved in the result record (FR-LPR-11).
    assert (body["workflow_id"], body["execution_id"], body["step_id"], body["correlation_id"]) == (
        "wf_1",
        "exec_1",
        "step_resolve_profile",
        "corr_1",
    )


def test_search_hit_resolves_then_persists() -> None:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json=[
                {"profileId": "smi-other", "displayName": "smi-learner match", "did": "did:x"},
                {"profileId": "smi-learner-1", "displayName": "Ada", "did": DID},
            ],
        )

    tc, _ = _app(handle)
    first = tc.post(ENDPOINT, json=_request("profile_id", "smi-learner-1")).json()
    assert first["status"] == "succeeded"
    assert first["result"]["resolution_method"] == "searched"
    assert first["result"]["did"] == DID
    assert calls[0].url.path == "/api/search/profiles/smi-learner-1"

    # Second call is served from the store — no second search.
    second = tc.post(ENDPOINT, json=_request("profile_id", "smi-learner-1")).json()
    assert second["result"]["resolution_method"] == "stored"
    assert len(calls) == 1


def test_search_miss_is_unresolved() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        # Fuzzy displayName hit but no exact handle match -> not a resolution.
        return httpx.Response(200, json=[{"profileId": "someone-else", "did": "did:y"}])

    tc, _ = _app(handle)
    body = tc.post(ENDPOINT, json=_request("profile_id", "smi-learner-1")).json()
    assert body["status"] == "unresolved"
    assert body["result"] is None
    assert body["error"] is None


def test_email_is_unresolved_without_api_call() -> None:
    tc, _ = _app(_no_call)
    body = tc.post(ENDPOINT, json=_request("email", "learner@example.com")).json()
    assert body["status"] == "unresolved"


def test_learncard_error_is_normalized_to_failed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    tc, _ = _app(handle)
    resp = tc.post(ENDPOINT, json=_request("profile_id", "smi-learner-1"))
    assert resp.status_code == 200  # normalized, not leaked
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"]["message"]


def test_invalid_learner_id_type_is_422() -> None:
    tc, _ = _app(_no_call)
    resp = tc.post(ENDPOINT, json=_request("phone", "+15551234567"))
    assert resp.status_code == 422


def test_healthz() -> None:
    tc, _ = _app(_no_call)
    assert tc.get("/healthz").json() == {"status": "ok"}


def test_service_env_and_token_load_regardless_of_cwd(tmp_path, monkeypatch) -> None:
    # The service .env (own db_path + the shared LEARNCARD_ token) must load even when the
    # process runs from a different CWD than the service dir — the repo-root-vs-service-dir
    # bug behind the empty-token "Authorization: Bearer " crash. Anchored env_file fixes it.
    from learncard_profile_resolver.config import ENV_FILE

    for var in ("LEARNCARD_PROFILE_RESOLVER_DB_PATH", "LEARNCARD_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)  # a CWD that is NOT the service dir
    original = ENV_FILE.read_text() if ENV_FILE.exists() else None
    ENV_FILE.write_text("LEARNCARD_PROFILE_RESOLVER_DB_PATH=:memory:\nLEARNCARD_API_TOKEN=tok-xyz\n")
    try:
        assert Settings().db_path == ":memory:"  # service-prefixed var, own Settings
        assert LearnCardSettings(_env_file=ENV_FILE).api_token == "tok-xyz"  # type: ignore[call-arg]
    finally:
        if original is None:
            ENV_FILE.unlink()
        else:
            ENV_FILE.write_text(original)
