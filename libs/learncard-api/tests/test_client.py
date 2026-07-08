"""Tests for the shared LearnCard REST client — no network, MockTransport only."""

from __future__ import annotations

import httpx
import pytest
from learncard_api import LearnCardClient, LearnCardSettings


def _client(handler: httpx.MockTransport) -> LearnCardClient:
    settings = LearnCardSettings(api_url="https://net.example/api", api_token="tok-123")
    return LearnCardClient(settings, transport=handler)


def test_get_attaches_bearer_and_joins_base_url() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"profileId": "smi-issuer"})

    with _client(httpx.MockTransport(handle)) as client:
        body = client.get("/profile")

    assert body == {"profileId": "smi-issuer"}
    assert str(seen[0].url) == "https://net.example/api/profile"
    assert seen[0].headers["Authorization"] == "Bearer tok-123"


def test_post_sends_json_body() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"sent": True})

    payload = {"type": "boost", "recipient": "learner@example.com"}
    with _client(httpx.MockTransport(handle)) as client:
        body = client.post("/send", json=payload)

    assert body == {"sent": True}
    assert seen[0].method == "POST"
    import json as _json

    assert _json.loads(seen[0].content) == payload


def test_raises_on_error_response() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    with _client(httpx.MockTransport(handle)) as client:  # noqa: SIM117
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/profile")


def test_request_returns_raw_response_for_bare_string_body() -> None:
    # POST /credential/send/{profileId} replies with a bare JSON string (the URI).
    uri = "lc:network:network.learncard.com/trpc:credential:abc-123"

    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=uri)

    with _client(httpx.MockTransport(handle)) as client:
        resp = client.request("POST", "/credential/send/@learner", json={"credential": {}})

    assert resp.json() == uri


def test_settings_read_from_dotenv_file(tmp_path, monkeypatch) -> None:
    # Regression: a consuming service's populated .env must actually be read.
    # With env_prefix alone (no env_file) a real .env is silently ignored and
    # api_token stays "" — producing the rejected "Authorization: Bearer " header.
    monkeypatch.delenv("LEARNCARD_API_TOKEN", raising=False)
    monkeypatch.delenv("LEARNCARD_API_URL", raising=False)
    (tmp_path / ".env").write_text("LEARNCARD_API_TOKEN=real-token-value\n")
    monkeypatch.chdir(tmp_path)

    assert LearnCardSettings().api_token == "real-token-value"
