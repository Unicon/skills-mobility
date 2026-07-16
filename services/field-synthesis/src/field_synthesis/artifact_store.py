"""File-based JSON artifact store (design §16 / ADR-0014).

Synthesis-result artifacts and invocation logs are written to local JSON files keyed
by execution_id. This keeps local dev/test free of any running store while preserving
the interface a cloud storage layer will back in AWS.

The store also supports loading synthesis-request artifacts (Field Mapping's output)
so the service can resolve by-ref requests without a live source-system call.

Failed artifacts are stored with their validation errors attached, so the audit trail
records rejected attempts (FR-FS-10). A failed record cannot be loaded as a
successful synthesis result.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import SynthesisRequestArtifact, SynthesisResultArtifact


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

    def _write(self, kind: str, key: str, record: dict[str, Any]) -> str:
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2))
        return f"{kind}:{key}"

    # --- synthesis result artifacts ---

    def store_synthesis_result(self, artifact: SynthesisResultArtifact) -> str:
        """Persist a successful synthesis result artifact; returns ``"synthesis_result:<key>"``."""
        key = artifact.execution_id
        return self._write(
            "synthesis_result",
            key,
            {"status": "succeeded", "artifact": artifact.model_dump(mode="json")},
        )

    def store_failed(self, execution_id: str, reason: str) -> str:
        """Persist a failed-synthesis record; returns ``"synthesis_result:failed:<key>"``.

        The record is written to the same path as a successful artifact so that
        a subsequent ``load_synthesis_result`` attempt raises ``FailedArtifactError``
        (audit trail, FR-FS-10). A separate ref distinguishes it from a success ref.
        """
        key = execution_id
        self._write("synthesis_result", key, {"status": "failed", "reason": reason})
        return f"synthesis_result:failed:{key}"

    def load_synthesis_result(self, ref: str) -> SynthesisResultArtifact:
        """Load a successful synthesis result artifact by ref."""
        record = self._read(ref)
        if record.get("status") != "succeeded":
            reason = record.get("reason") or "artifact generation failed"
            raise FailedArtifactError([str(reason)])
        artifact_data: dict[str, Any] = record["artifact"]
        return SynthesisResultArtifact(**artifact_data)

    # --- synthesis request artifacts (Field Mapping output, loaded by ref) ---

    def load_synthesis_request(self, ref: str) -> SynthesisRequestArtifact:
        """Load a synthesis-request artifact written by the Field Mapping service."""
        record = self._read(ref)
        raw = record.get("artifact", record)
        artifact_data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        return SynthesisRequestArtifact(**artifact_data)

    # --- invocation log ---

    def store_invocation_log(self, record: dict[str, Any], key: str) -> str:
        """Persist an invocation log record; returns ``"llmcall:<key>"``."""
        return self._write("llmcall", key, record)

    def _read(self, ref: str) -> dict[str, Any]:
        # refs: "synthesis_result:<key>", "synthesis_request:<key>", "llmcall:<key>"
        # "synthesis_result:failed:<key>" → kind="synthesis_result", key="failed:<key>"
        # Split on first ":" only; remainder is the key (may itself contain colons).
        parts = ref.split(":", 1)
        kind = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        path = self._path(kind, key)
        if not path.exists():
            raise ArtifactNotFoundError(f"artifact not found: {ref}")
        data: dict[str, Any] = json.loads(path.read_text())
        return data
