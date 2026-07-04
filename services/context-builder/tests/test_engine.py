"""Unit tests for the engine internals — especially `_dig` path-walking and the
`for_each.where` / `select` criterion resolution that integration tests only
exercise indirectly."""

from __future__ import annotations

from context_builder.engine import _MISSING, _crit_match, _dig, _resolve, _run_for_each
from context_builder.profiles import Step

# --- _dig -------------------------------------------------------------------


def test_dig_walks_nested_dicts():
    assert _dig({"a": {"b": {"c": 1}}}, "a.b.c") == 1


def test_dig_numeric_segment_indexes_into_list():
    assert _dig({"items": [{"id": "x"}, {"id": "y"}]}, "items.1.id") == "y"
    assert _dig([{"id": "z"}], "0.id") == "z"  # the profile's user_id path: "0.id"


def test_dig_missing_key_returns_sentinel():
    assert _dig({"a": 1}, "b") is _MISSING
    assert _dig({"a": {"b": 1}}, "a.c") is _MISSING


def test_dig_list_index_out_of_range_returns_sentinel():
    assert _dig([{"id": "a"}], "5.id") is _MISSING


def test_dig_non_numeric_segment_into_list_returns_sentinel():
    assert _dig([{"id": "a"}], "name") is _MISSING


def test_dig_walking_into_scalar_returns_sentinel():
    assert _dig({"a": 5}, "a.b") is _MISSING  # 5 is neither dict nor list


# --- _resolve ---------------------------------------------------------------


def test_resolve_each_source():
    event = {"body": {"x": "EV"}}
    responses = {"step1": {"y": "RE"}}
    assert _resolve({"source": "event", "path": "body.x"}, event, responses, None) == "EV"
    resp_spec = {"source": "response", "step": "step1", "path": "y"}
    assert _resolve(resp_spec, event, responses, None) == "RE"
    assert _resolve({"source": "foreach_item", "path": "z"}, event, responses, {"z": "FI"}) == "FI"
    assert _resolve({"source": "bogus"}, event, responses, None) is _MISSING


# --- _crit_match (static value vs source spec) ------------------------------


def test_crit_match_static_value():
    assert _crit_match({"type": "Page"}, "type", "Page", {}, {}) is True
    assert _crit_match({"type": "Assignment"}, "type", "Page", {}, {}) is False


def test_crit_match_dynamic_source_spec():
    event = {"body": {"aid": "A1"}}
    spec = {"source": "event", "path": "body.aid"}
    assert _crit_match({"content_id": "A1"}, "content_id", spec, event, {}) is True
    assert _crit_match({"content_id": "A2"}, "content_id", spec, event, {}) is False


# --- _run_for_each ----------------------------------------------------------


def _pages_step(where: dict) -> Step:
    return Step(
        output_key="pages",
        endpoint="/p/{cid}",
        params={"cid": {"source": "foreach_item", "path": "content_id"}},
        for_each={"source": "response", "step": "mod", "path": "items", "where": where},
    )


def test_run_for_each_static_where_filters(fake_client):
    responses = {
        "mod": {"items": [
            {"type": "Page", "content_id": "P1"},
            {"type": "Assignment", "content_id": "A1"},
        ]}
    }
    client = fake_client({"/p/P1": (200, {"id": "P1"})})
    out = _run_for_each(client, _pages_step({"type": "Page"}), {}, responses)
    assert out == [{"id": "P1"}]
    assert client.calls == ["/p/P1"]  # the Assignment item was filtered out


def test_run_for_each_where_resolves_event_sourced_value(fake_client):
    # The capability added to match select.contains_item: a where value can be
    # sourced from the event, not just a static string.
    event = {"body": {"wanted_type": "Page"}}
    responses = {
        "mod": {"items": [
            {"type": "Page", "content_id": "P1"},
            {"type": "Quiz", "content_id": "Q1"},
        ]}
    }
    step = _pages_step({"type": {"source": "event", "path": "body.wanted_type"}})
    client = fake_client({"/p/P1": (200, {"id": "P1"})})
    out = _run_for_each(client, step, event, responses)
    assert out == [{"id": "P1"}]
    assert client.calls == ["/p/P1"]
