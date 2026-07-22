import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import field_mapping

CATALOGS = Path(field_mapping.__file__).parent / "catalogs"
SOURCES = sorted((CATALOGS / "sources").rglob("*.openapi.json"))
TARGETS = sorted((CATALOGS / "targets").rglob("*.openapi.json"))

# The seven resources the Context Builder skill_mastered.v1 fetch profile fetches
# (services/context-builder/.../fetch_profiles/skill_mastered.yaml output_keys).
_SKILL_MASTERED_RESOURCES = {
    "outcome",
    "assignment",
    "rubric",
    "module_context",
    "module_pages",
    "canvas_user",
    "submission",
}

# The eight resources the Context Builder course_completed.v1 fetch profile fetches
# (services/context-builder/.../fetch_profiles/course_completed.yaml output_keys).
_COURSE_COMPLETED_RESOURCES = {
    "course",
    "learner_profile",
    "enrollment",
    "modules",
    "pages",
    "assignments",
    "rubrics",
    "submissions",
}


def _schemas(path: Path) -> Iterator[dict[str, Any]]:
    doc = json.loads(path.read_text())
    yield from doc["components"]["schemas"].values()


def _leaf_fields(schema: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield terminal (mappable) fields, descending through nested objects and
    arrays-of-objects."""
    for name, node in schema.get("properties", {}).items():
        if "properties" in node:
            yield from _leaf_fields(node)
        elif node.get("type") == "array" and "properties" in (node.get("items") or {}):
            yield from _leaf_fields(node["items"])
        else:
            yield name, node


def test_all_catalog_files_parse_and_carry_required_extensions() -> None:
    assert SOURCES, "no source catalogs found"
    assert TARGETS, "no target catalogs found"
    for path in SOURCES:
        for schema in _schemas(path):
            assert schema.get("x-source-system") == "mock_lms", path.name
            assert schema.get("x-resource-schema-id"), path.name
    for path in TARGETS:
        for schema in _schemas(path):
            assert schema.get("x-transformation-type"), path.name


def test_skill_mastered_profile_lists_context_builder_resources() -> None:
    mapping = json.loads(
        (CATALOGS / "fetch_profiles" / "mock_lms" / "skill_mastered.v1.json").read_text()
    )
    assert set(mapping["resources"]) == _SKILL_MASTERED_RESOURCES
    # Every listed resource has a matching source-resource catalog.
    resource_ids = {
        schema["x-resource-schema-id"] for path in SOURCES for schema in _schemas(path)
    }
    assert _SKILL_MASTERED_RESOURCES <= resource_ids


def test_course_completed_profile_lists_context_builder_resources() -> None:
    mapping = json.loads(
        (CATALOGS / "fetch_profiles" / "mock_lms" / "course_completed.v1.json").read_text()
    )
    assert set(mapping["resources"]) == _COURSE_COMPLETED_RESOURCES
    # Every listed resource has a matching source-resource catalog.
    resource_ids = {
        schema["x-resource-schema-id"] for path in SOURCES for schema in _schemas(path)
    }
    assert _COURSE_COMPLETED_RESOURCES <= resource_ids


def test_every_target_field_declares_no_mapping_behavior() -> None:
    for path in TARGETS:
        for schema in _schemas(path):
            for name, node in _leaf_fields(schema):
                assert "x-no-mapping-behavior" in node, f"{path.name}:{name}"
