"""HttpxLMSClient — bracket-param encoding for Lambda Function URL targets."""

from __future__ import annotations

import httpx
from context_builder.lms_client import HttpxLMSClient, _encode_bracket_params


def test_encode_bracket_params_encodes_query_brackets_only() -> None:
    assert (
        _encode_bracket_params("/api/v1/accounts/1/users?uuids[]=abc")
        == "/api/v1/accounts/1/users?uuids%5B%5D=abc"
    )
    assert (
        _encode_bracket_params("/api/v1/courses/C-1/modules?include[]=items")
        == "/api/v1/courses/C-1/modules?include%5B%5D=items"
    )
    # No query string → untouched.
    assert _encode_bracket_params("/api/v1/courses/C-1") == "/api/v1/courses/C-1"


def test_client_sends_encoded_brackets_on_the_wire() -> None:
    # Lambda Function URLs mishandle literal brackets in query strings; the
    # request must leave the client percent-encoded (uvicorn decodes them
    # identically, so local behaviour is unchanged).
    seen: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=[])

    client = HttpxLMSClient("http://lms.example")
    client._client = httpx.Client(
        base_url="http://lms.example", transport=httpx.MockTransport(handle)
    )
    resp = client.get("/api/v1/accounts/1/users?uuids[]=7c4f-820d")

    assert resp.status_code == 200
    assert seen == ["http://lms.example/api/v1/accounts/1/users?uuids%5B%5D=7c4f-820d"]
