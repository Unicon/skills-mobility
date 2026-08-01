"""§11 Layer-A validation gates for a Field Mapping generation.

These are hard gates (ADR-0013 Layer A): a structurally valid response is never a
success on its own (FR-FM-14 / FR-FM-27). ``validate_generation`` returns the list
of validation errors — empty means the generation passed. Invalid generations are
stored as failed artifacts with these errors attached (§11), never as successful
mappings. Nothing here executes the JSONata; the parse gate is parse-only.
"""

from __future__ import annotations

import re
from typing import Any

import jsonata  # type: ignore[import-untyped]

from .contracts import MappingGeneration, MappingRequest

# Matches `source_payloads.<alias>[.<seg>...]` references inside a JSONata body.
_SOURCE_REF = re.compile(
    r"\bsource_payloads\.([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
)


def validate_generation(
    generation: MappingGeneration,
    *,
    request: MappingRequest,
    target_schema: dict[str, Any],
) -> list[str]:
    """Run the §11 gates against a model generation. Returns errors (empty = pass)."""
    errors: list[str] = []
    _check_placeholder_bijection(generation, errors)  # §11.3
    _check_jsonata_parses(generation.jsonata, errors)  # §11.4
    _check_source_paths(generation.jsonata, request.source_payloads, errors)  # §11.5
    _check_target_required_fields(generation.jsonata, target_schema, errors)  # §11.6
    _check_synthesis_permission(generation, request, errors)  # §6 hard constraint
    _check_confidence_rationale(generation, errors)  # FR-FM-14
    return errors


def _check_placeholder_bijection(g: MappingGeneration, errors: list[str]) -> None:
    placeholder_ids = set(g.placeholder_ids)
    request_ids = {r.placeholder_id for r in g.synthesis_requests}
    for pid in sorted(placeholder_ids - request_ids):
        errors.append(f"placeholder '{pid}' has no synthesis request")
    for rid in sorted(request_ids - placeholder_ids):
        errors.append(f"synthesis request '{rid}' has no matching placeholder id")


def _check_jsonata_parses(expr: str, errors: list[str]) -> None:
    # Parse-only (no evaluate()): a syntax error surfaces as JException at compile.
    try:
        jsonata.Jsonata(expr)
    except Exception as ex:
        errors.append(f"jsonata parse error: {ex}")


def _check_source_paths(
    expr: str, source_payloads: dict[str, Any], errors: list[str]
) -> None:
    # Confirms every `source_payloads.*` reference the model emitted actually resolves
    # against the payloads we supplied — catches hallucinated source fields.
    for path in sorted({m.group(1) for m in _SOURCE_REF.finditer(expr)}):
        segments = path.split(".")
        alias = segments[0]
        if alias not in source_payloads:
            errors.append(f"jsonata references unknown source payload '{alias}'")
            continue
        # Walk deeper only through dicts; stop at arrays/scalars (can't statically verify).
        current: Any = source_payloads[alias]
        for seg in segments[1:]:
            if not isinstance(current, dict):
                break
            if seg not in current:
                errors.append(f"jsonata references unknown source path 'source_payloads.{path}'")
                break
            current = current[seg]


def _check_target_required_fields(
    expr: str, target_schema: dict[str, Any], errors: list[str]
) -> None:
    # Top-level required: positional check against the outermost constructor keys.
    required = target_schema.get("required", [])
    keys = _top_level_object_keys(expr)
    for field in required:
        if field not in keys:
            errors.append(f"target requires field '{field}' but the mapping output omits it")
    # Nested required (#125): flag a required leaf only when the mapping
    # CONSTRUCTS its parent object but omits the leaf (JSON Schema semantics —
    # `required` inside an optional branch binds only when that branch exists;
    # a wholly omitted optional object is fine). Presence-only, not positional —
    # a key in the wrong branch still passes here and is caught by the
    # Transformation Executor's real jsonschema validation; this layer exists so
    # FM stops reporting "succeeded" for mappings that build e.g. `achievement`
    # without its required `name`/`description` (the live failure mode).
    all_keys = _all_object_keys(expr)
    for path in _nested_required_paths(target_schema):
        segments = path.split(".")
        parent, leaf = segments[-2], segments[-1]
        if parent in all_keys and leaf not in all_keys:
            errors.append(
                f"target requires nested field '{path}' but the mapping output omits it"
            )


def _nested_required_paths(schema: dict[str, Any]) -> list[str]:
    """All required property paths BELOW the top level (dotted; array items keep
    their parent's path). Local ``#/$defs/...`` refs are resolved; cycles guarded."""
    defs = schema.get("$defs", {})
    paths: list[str] = []

    def resolve(node: dict[str, Any], seen: frozenset[str]) -> dict[str, Any]:
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            name = ref.removeprefix("#/$defs/")
            if name in seen or name not in defs:
                return {}
            return resolve(defs[name], seen | {name})
        return node

    def walk(node: dict[str, Any], prefix: str, seen: frozenset[str], top: bool) -> None:
        node = resolve(node, seen)
        for field in node.get("required", []) if not top else []:
            paths.append(f"{prefix}{field}")
        for key, sub in (node.get("properties") or {}).items():
            if isinstance(sub, dict):
                walk(sub, f"{prefix}{key}.", seen, top=False)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, prefix, seen, top=False)

    # Descend from the top-level properties so top-level required (handled
    # positionally above) isn't duplicated.
    for key, sub in (schema.get("properties") or {}).items():
        if isinstance(sub, dict):
            walk(sub, f"{key}.", frozenset(), top=False)
    items = schema.get("items")
    if isinstance(items, dict):
        walk(items, "", frozenset(), top=False)
    return sorted(set(paths))


def _all_object_keys(expr: str) -> set[str]:
    """Every object-constructor key at ANY depth (same tokenizer discipline as
    _top_level_object_keys, without the depth filter)."""
    keys: set[str] = set()
    stack: list[bool] = []
    i, n = 0, len(expr)
    while i < n:
        c = expr[i]
        if c in "\"'":
            j, buf = i + 1, []
            while j < n:
                if expr[j] == "\\" and j + 1 < n:
                    buf.append(expr[j + 1])
                    j += 2
                    continue
                if expr[j] == c:
                    break
                buf.append(expr[j])
                j += 1
            literal = "".join(buf)
            k = j + 1
            while k < n and expr[k] in " \t\r\n":
                k += 1
            if k < n and expr[k] == ":" and stack and stack[-1]:
                keys.add(literal)
            i = j + 1
            continue
        if c == "{":
            stack.append(True)
        elif c == "[":
            stack.append(False)
        elif c in "}]" and stack:
            stack.pop()
        i += 1
    return keys


def _check_synthesis_permission(
    g: MappingGeneration, request: MappingRequest, errors: list[str]
) -> None:
    # §6: when synthesis is forbidden, no field may be synthesis-backed.
    if not request.synthesis_allowed and (g.placeholder_ids or g.synthesis_requests):
        errors.append(
            "synthesis_allowed is false but the mapping contains placeholders / synthesis requests"
        )


def _check_confidence_rationale(g: MappingGeneration, errors: list[str]) -> None:
    if g.confidence is None:
        errors.append("missing confidence")
    if not g.rationale:
        errors.append("missing rationale")


def _top_level_object_keys(expr: str) -> set[str]:
    """Best-effort static extraction of the outermost object-constructor keys from a
    JSONata expression (no execution). Handles nested objects/arrays and string
    literals; only keys directly inside the outermost object are returned."""
    keys: set[str] = set()
    stack: list[bool] = []  # True where the open container is an object
    expect_key = False
    i, n = 0, len(expr)
    while i < n:
        c = expr[i]
        if c in "\"'":
            j, buf = i + 1, []
            while j < n:
                if expr[j] == "\\" and j + 1 < n:
                    buf.append(expr[j + 1])
                    j += 2
                    continue
                if expr[j] == c:
                    break
                buf.append(expr[j])
                j += 1
            if expect_key and len(stack) == 1 and stack[-1]:
                k = j + 1
                while k < n and expr[k] in " \t\r\n":
                    k += 1
                if k < n and expr[k] == ":":
                    keys.add("".join(buf))
            i, expect_key = j + 1, False
            continue
        if c == "{":
            stack.append(True)
            expect_key = True
        elif c == "[":
            stack.append(False)
            expect_key = False
        elif c in "}]":
            if stack:
                stack.pop()
            expect_key = False
        elif c == ",":
            expect_key = bool(stack) and stack[-1]
        elif c not in " \t\r\n":
            expect_key = False
        i += 1
    return keys
