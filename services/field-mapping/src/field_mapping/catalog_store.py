"""Resolve source-resource, fetch-profile, and target catalogs (design §5).

The Orchestrator never supplies catalog/data-dictionary ids (FR-FM-5, §4);
resolution is service-internal, keyed by ``source_system + resource_schema_id``,
``source_system + fetch_profile_id``, and ``delivery_target + transformation_type``
(``transformation_type`` only for ``credential_template``, which has no target
subdirectory).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DeliveryTarget, TransformationType

_CATALOGS_DIR = Path(__file__).resolve().parent / "catalogs"


class CatalogNotFoundError(Exception):
    """A requested catalog is not authored / does not resolve."""


def _load_single_schema(path: Path) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(path.read_text())
    schemas: dict[str, Any] = doc["components"]["schemas"]
    # Each catalog file defines exactly one schema.
    schema: dict[str, Any] = next(iter(schemas.values()))
    return schema


class CatalogStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or _CATALOGS_DIR

    def resolve_fetch_profile(self, *, source_system: str, fetch_profile_id: str) -> dict[str, Any]:
        path = self._base / "fetch_profiles" / source_system / f"{fetch_profile_id}.json"
        if not path.exists():
            raise CatalogNotFoundError(f"no fetch profile for {source_system}/{fetch_profile_id}")
        profile: dict[str, Any] = json.loads(path.read_text())
        return profile

    def resolve_source_catalog(
        self, *, source_system: str, resource_schema_id: str
    ) -> dict[str, Any]:
        path = self._base / "sources" / source_system / f"{resource_schema_id}.openapi.json"
        if not path.exists():
            raise CatalogNotFoundError(
                f"no source catalog for {source_system}/{resource_schema_id}"
            )
        return _load_single_schema(path)

    def resolve_source_catalogs(
        self, *, source_system: str, fetch_profile_id: str
    ) -> dict[str, dict[str, Any]]:
        profile = self.resolve_fetch_profile(
            source_system=source_system, fetch_profile_id=fetch_profile_id
        )
        return {
            resource_id: self.resolve_source_catalog(
                source_system=source_system, resource_schema_id=resource_id
            )
            for resource_id in profile["resources"]
        }

    def resolve_target(
        self,
        *,
        transformation_type: TransformationType,
        delivery_target: DeliveryTarget | None,
    ) -> dict[str, Any]:
        targets = self._base / "targets"
        filename = f"{transformation_type}.openapi.json"
        if transformation_type is TransformationType.CREDENTIAL_TEMPLATE:
            # No delivery_target for this phase (ADR-0017); keyed by type only.
            path = targets / "credential_template" / filename
        else:
            if delivery_target is None:
                raise CatalogNotFoundError(f"{transformation_type} requires a delivery_target")
            path = targets / str(delivery_target) / filename
        if not path.exists():
            raise CatalogNotFoundError(
                f"no target catalog for {delivery_target}/{transformation_type}"
            )
        return _load_single_schema(path)
