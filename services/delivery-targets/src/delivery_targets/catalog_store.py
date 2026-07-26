"""Resolve the available-delivery-targets catalog (design §5).

The Orchestrator does not enumerate targets in the request (FR-DT-5); the service
loads the catalog from its own committed JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CATALOGS_DIR = Path(__file__).resolve().parent / "catalogs"
_CATALOG_FILE = "available_delivery_targets.json"


class CatalogError(Exception):
    """The available-delivery-targets catalog could not be loaded."""


class CatalogStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base = base_dir or _CATALOGS_DIR

    def load_targets(self) -> list[dict[str, Any]]:
        """Return the full available-delivery-targets catalog as a list of dicts."""
        path = self._base / _CATALOG_FILE
        if not path.exists():
            raise CatalogError(f"available-delivery-targets catalog not found: {path}")
        catalog: list[dict[str, Any]] = json.loads(path.read_text())
        return catalog
