"""HttpxLMSClient — bracket-param encoding for Lambda Function URL targets."""

from __future__ import annotations

import httpx
from context_builder.lms_client import HttpxLMSClient


def _wire_client(seen: list[str]) -> HttpxLMSClient:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json=[])

    client = HttpxLMSClient("http://lms.example")
    client._client = httpx.Client(
        base_url="http://lms.example", transport=httpx.MockTransport(handle)
    )
    return client


def test_encodes_bracket_params_on_the_wire() -> None:
    # Lambda Function URLs mishandle literal brackets in query strings; the
    # request must leave the client percent-encoded (uvicorn decodes them
    # identically, so local behaviour is unchanged).
    seen: list[str] = []
    resp = _wire_client(seen).get("/api/v1/accounts/1/users?uuids[]=7c4f-820d")

    assert resp.status_code == 200
    assert seen == ["http://lms.example/api/v1/accounts/1/users?uuids%5B%5D=7c4f-820d"]


def test_no_query_string_is_untouched() -> None:
    seen: list[str] = []
    _wire_client(seen).get("/api/v1/courses/C-1")

    assert seen == ["http://lms.example/api/v1/courses/C-1"]


def test_already_encoded_brackets_are_not_double_encoded() -> None:
    # "%" is in the safe set, so pre-encoded input passes through unchanged.
    seen: list[str] = []
    _wire_client(seen).get("/api/v1/courses/C-1/modules?include%5B%5D=items")

    assert seen == ["http://lms.example/api/v1/courses/C-1/modules?include%5B%5D=items"]
