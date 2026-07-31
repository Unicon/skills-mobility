"""File-based JSON artifact store (design §14 / ADR-0014).

Selection artifacts and invocation logs are written to local JSON files keyed by
execution_id. This keeps local dev/test free of any running store while preserving
the interface a cloud storage layer will back in AWS.

Failed artifacts are stored too, with their validation errors attached under a
separate ``selection_failed`` kind, so the audit trail records rejected attempts
(FR-DT-21) without a failed attempt ever overwriting a stored success. A failed
record cannot be loaded as a successful selection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import SelectionArtifact


class FailedArtifactError(Exception):
    """Raised when a ref resolves to a stored *failed* artifact."""

    def __init__(self, validation_errors: list[str]) -> None:
        self.validation_errors = validation_errors
        super().__init__("; ".join(validation_errors) or "artifact generation failed")


class ArtifactNotFoundError(Exception):
    """Raised when a ref does not resolve to any stored artifact."""


class ArtifactStore:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def _path(self, kind: str, key: str) -> Path:
        return self._base / kind / f"{key}.json"

    def _write(self, kind: str, key: str, record: dict[str, object]) -> str:
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2))
        return f"{kind}:{key}"

    # --- selection artifacts ---

    def store_selection(self, artifact: SelectionArtifact) -> str:
        """Persist a successful selection artifact; returns ``"selection:<key>"``."""
        key = artifact.execution_id
        return self._write(
            "selection", key, {"status": "succeeded", "artifact": artifact.model_dump(mode="json")}
        )

    def store_failed(self, execution_id: str, reason: str) -> str:
        """Persist a failed-selection record; returns the loadable
        ``"selection_failed:<key>"`` ref.

        Failures live under their own kind so a failed attempt never overwrites a
        previously-stored successful selection for the same key (defensive — the
        key is execution_id, but the store must not be able to destroy a success).
        The rejected attempt stays auditable (FR-DT-21): loading the returned ref
        raises ``FailedArtifactError``, not a not-found error.
        """
        return self._write("selection_failed", execution_id, {"status": "failed", "reason": reason})

    def load_selection(self, ref: str) -> SelectionArtifact:
        """Load a successful selection artifact by ref."""
        record = self._read(ref)
        if record.get("status") != "succeeded":
            raise FailedArtifactError(
                [record.get("reason", "artifact generation failed")]
            )
        artifact_data: dict[str, Any] = record["artifact"]
        return SelectionArtifact(**artifact_data)

    # --- invocation log ---

    def store_invocation_log(self, record: dict[str, Any], key: str) -> str:
        """Persist an invocation log record; returns ``"llmcall:<key>"``."""
        return self._write("llmcall", key, record)

    def _read(self, ref: str) -> dict[str, Any]:
        # refs look like "selection:<key>", "selection_failed:<key>" or "llmcall:<key>"
        kind, key = ref.split(":", 1)
        path = self._path(kind, key)
        if not path.exists():
            raise ArtifactNotFoundError(f"artifact not found: {ref}")
        data: dict[str, Any] = json.loads(path.read_text())
        return data
