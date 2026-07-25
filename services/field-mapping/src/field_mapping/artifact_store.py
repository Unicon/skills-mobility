"""File-based JSON artifact store (design §17).

Mapping and synthesis-request artifacts are written to local JSON files keyed by
a stable id derived from ``source_system + fetch_profile_id + transformation_type
+ delivery_target``. This keeps local dev/test free of any running store while
preserving the interface a cloud storage layer will back in AWS.

Failed artifacts are stored too, with their validation errors attached, so the
audit trail records rejected attempts (§11). A failed record cannot be loaded as
a successful artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import (
    DeliveryTarget,
    MappingArtifact,
    SynthesisRequestArtifact,
    TransformationType,
)


class FailedArtifactError(Exception):
    """Raised when a ref resolves to a stored *failed* artifact."""

    def __init__(self, validation_errors: list[str]) -> None:
        self.validation_errors = validation_errors
        super().__init__("; ".join(validation_errors) or "artifact generation failed")


def stable_key(
    *,
    source_system: str,
    fetch_profile_id: str,
    transformation_type: TransformationType,
    delivery_target: DeliveryTarget | None,
) -> str:
    """The stable artifact id shared by a request's mapping, synthesis-request, and
    invocation-log records (§17)."""
    parts = [source_system, fetch_profile_id, str(transformation_type)]
    if delivery_target is not None:
        parts.append(str(delivery_target))
    return "_".join(parts)


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

    # --- mapping artifacts ---

    def store_mapping(self, artifact: MappingArtifact) -> str:
        key = stable_key(
            source_system=artifact.source_system,
            fetch_profile_id=artifact.fetch_profile_id,
            transformation_type=artifact.transformation_type,
            delivery_target=artifact.delivery_target,
        )
        return self._write(
            "mapping", key, {"status": "succeeded", "artifact": artifact.model_dump(mode="json")}
        )

    def store_failed_mapping(
        self,
        *,
        source_system: str,
        fetch_profile_id: str,
        transformation_type: TransformationType,
        delivery_target: DeliveryTarget | None,
        validation_errors: list[str],
    ) -> str:
        key = stable_key(
            source_system=source_system,
            fetch_profile_id=fetch_profile_id,
            transformation_type=transformation_type,
            delivery_target=delivery_target,
        )
        return self._write(
            "mapping",
            key,
            {"status": "failed", "artifact": None, "validation_errors": validation_errors},
        )

    def load_mapping(self, ref: str) -> MappingArtifact:
        record = self._read(ref)
        if record["status"] != "succeeded":
            raise FailedArtifactError(list(record.get("validation_errors", [])))
        return MappingArtifact(**record["artifact"])

    # --- synthesis-request artifacts ---

    def store_synthesis_request(self, artifact: SynthesisRequestArtifact, *, key: str) -> str:
        return self._write(
            "synthesis", key, {"status": "succeeded", "artifact": artifact.model_dump(mode="json")}
        )

    def load_synthesis_request(self, ref: str) -> SynthesisRequestArtifact:
        record = self._read(ref)
        if record["status"] != "succeeded":
            raise FailedArtifactError(list(record.get("validation_errors", [])))
        return SynthesisRequestArtifact(**record["artifact"])

    # --- invocation log (§14, append-only) ---

    def store_invocation_log(self, record: dict[str, Any], *, key: str) -> str:
        """Append a new invocation-log record for ``key``.

        Each call writes to a distinct file at ``llmcall/<key>/<NNNN>.json``
        where NNNN is the zero-padded index of the next record (determined by
        counting existing files). This makes the log append-only so successive
        calls for the same input shape can be compared over time (design §14).

        Returns a ref of the form ``llmcall:<key>/<NNNN>`` pointing at this
        specific record.

        Note: the ``_reuse`` path in service.py constructs the synthetic ref
        ``llmcall:<key>`` (without a record index) because it has not written a
        new record — that ref now points to a directory, not a file. The reuse
        path is default-off and used only in production-like mode; it is clearly
        a directory-level ref rather than a specific record ref.
        """
        key_dir = self._base / "llmcall" / key
        key_dir.mkdir(parents=True, exist_ok=True)
        index = len(list(key_dir.glob("*.json")))
        record_name = f"{index:04d}"
        path = key_dir / f"{record_name}.json"
        path.write_text(json.dumps(record, indent=2))
        return f"llmcall:{key}/{record_name}"

    def _read(self, ref: str) -> dict[str, Any]:
        kind, key = ref.split(":", 1)
        data: dict[str, Any] = json.loads(self._path(kind, key).read_text())
        return data
