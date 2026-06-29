"""Deterministic fetch-profile execution engine.

Runs a profile's ordered steps against the LMS client and assembles the
``source_data`` map. Per-step behavior:

- ``condition`` (present/absent on a prior response field) → skip if unmet.
- ``select`` → from a list response, store the one matching element.
- ``for_each`` → run the step once per matching item from a prior response;
  collect a list.
- otherwise → a single fetch stored under ``output_key``.

A failed LMS call is stored as a structured error object under its output key
(the bundle is still returned). A required identifier that cannot be resolved
for a non-conditional step raises ``MissingIdentifier`` → the builder turns that
into a failure response (FR-CB11).
"""

from __future__ import annotations

import logging
from typing import Any

from context_builder.lms_client import LMSClient
from context_builder.profiles import FetchProfile, Step
from context_builder.schemas import FetchError

logger = logging.getLogger(__name__)

_MISSING = object()


class MissingIdentifier(Exception):
    """A required identifier for a non-conditional step could not be resolved."""


def _dig(obj: Any, path: str) -> Any:
    """Walk a dot-path (numeric segments index into lists). ``_MISSING`` if absent."""
    cur = obj
    for seg in path.split("."):
        if isinstance(cur, dict):
            if seg not in cur:
                return _MISSING
            cur = cur[seg]
        elif isinstance(cur, list):
            if not seg.isdigit() or int(seg) >= len(cur):
                return _MISSING
            cur = cur[int(seg)]
        else:
            return _MISSING
    return cur


def _resolve(
    spec: dict[str, Any], event: dict[str, Any], responses: dict[str, Any], item: Any
) -> Any:
    """Resolve one param/criterion source spec to a value (or ``_MISSING``)."""
    source = spec.get("source")
    path = spec.get("path", "")
    if source == "event":
        return _dig(event, path)
    if source == "response":
        return _dig(responses.get(spec.get("step", ""), _MISSING), path)
    if source == "foreach_item":
        return _dig(item, path)
    return _MISSING


def _fill(
    endpoint: str,
    params: dict[str, dict[str, Any]],
    event: dict[str, Any],
    responses: dict[str, Any],
    item: Any,
) -> Any:
    """Substitute ``{name}`` placeholders in the endpoint. ``_MISSING`` if any
    placeholder param is unresolvable."""
    url = endpoint
    for name, spec in params.items():
        placeholder = "{" + name + "}"
        if placeholder not in url:
            continue
        value = _resolve(spec, event, responses, item)
        if value is _MISSING:
            return _MISSING
        url = url.replace(placeholder, str(value))
    return url


def _crit_match(
    it: dict[str, Any], key: str, spec: Any, event: dict[str, Any], responses: dict[str, Any]
) -> bool:
    expected = _resolve(spec, event, responses, None) if isinstance(spec, dict) else spec
    return bool(it.get(key) == expected)


def _select(
    response: Any, select: dict[str, Any], event: dict[str, Any], responses: dict[str, Any]
) -> Any:
    """Pick the list element whose nested list contains a matching item."""
    if not isinstance(response, list):
        return _MISSING
    contains = select["where"]["contains_item"]
    list_field = contains["in"]
    criteria = {k: v for k, v in contains.items() if k != "in"}
    for element in response:
        for it in element.get(list_field, []) if isinstance(element, dict) else []:
            if all(_crit_match(it, k, v, event, responses) for k, v in criteria.items()):
                return element
    return _MISSING


def _error(url: str, status_code: int | None, message: str) -> dict[str, Any]:
    # Per design §3, a failed fetch is stored as `{"error": {...}}` under its key.
    fetch_error = FetchError(source_api=f"GET {url}", status_code=status_code, message=message)
    return {"error": fetch_error.model_dump()}


def _fetch(client: LMSClient, url: str) -> Any:
    resp = client.get(url)
    logger.info("LMS fetch: GET %s -> %s", url, resp.status_code)  # FR-CB15: each call attempted
    if resp.status_code >= 400:
        message = str(resp.data.get("detail", "")) if isinstance(resp.data, dict) else ""
        return _error(url, resp.status_code, message)
    return resp.data


def _run_for_each(
    client: LMSClient, step: Step, event: dict[str, Any], responses: dict[str, Any]
) -> list[Any]:
    fe = step.for_each or {}
    source_list = _dig(responses.get(fe.get("step", ""), _MISSING), fe.get("path", ""))
    if source_list is _MISSING or not isinstance(source_list, list):
        return []
    where = fe.get("where", {})
    out: list[Any] = []
    for item in source_list:
        # `where` values may be static (e.g. `type: Page`) or source specs
        # ({source: event/response, path: ...}); _crit_match handles both, so
        # for_each filtering matches select's contains_item capability.
        if where and not all(
            _crit_match(item, k, v, event, responses) for k, v in where.items()
        ):
            continue
        url = _fill(step.endpoint, step.params, event, responses, item)
        if url is _MISSING:
            # An item whose params can't be resolved is intentionally skipped (the
            # for_each collects only resolvable items) — so the result list can be
            # shorter than the source list. Unlike a single-step fetch failure, this
            # is not surfaced as an error object; it means "this item didn't apply".
            logger.info("for_each '%s': skipped item with unresolvable url", step.output_key)
            continue
        out.append(_fetch(client, url))
    return out


def run_profile(profile: FetchProfile, event: dict[str, Any], client: LMSClient) -> dict[str, Any]:
    responses: dict[str, Any] = {}
    for step in profile.steps:
        if step.condition is not None:
            value = _resolve(step.condition, event, responses, None)
            present = value is not _MISSING and value is not None
            if step.condition.get("operator") == "present" and not present:
                continue
            if step.condition.get("operator") == "absent" and present:
                continue

        if step.for_each is not None:
            responses[step.output_key] = _run_for_each(client, step, event, responses)
            continue

        url = _fill(step.endpoint, step.params, event, responses, None)
        if url is _MISSING:
            raise MissingIdentifier(
                f"step '{step.output_key}': unresolved required identifier for {step.endpoint}"
            )
        result = _fetch(client, url)
        if step.select is not None and not (isinstance(result, dict) and "error" in result):
            selected = _select(result, step.select, event, responses)
            result = (
                selected
                if selected is not _MISSING
                else _error(url, None, "no matching element for select")
            )
        responses[step.output_key] = result
    return responses
