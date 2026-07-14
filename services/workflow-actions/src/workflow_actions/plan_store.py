"""File-based JSON plan store (design §14 / ADR-0014).

Delivery-phase plan artifacts are stored to local JSON files keyed by the
applicability signature (event_type + source_system + sorted selected_targets).
This keeps local dev/test free of any running store while preserving the interface
a cloud storage layer will back in AWS.

Failed plan records are stored with their validation errors so the audit trail
captures rejected attempts. A failed record cannot be loaded as a successful plan.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import DeliveryPhasePlan


class FailedPlanError(Exception):
    """Raised when a ref resolves to a stored *failed* plan artifact."""

    def __init__(self, validation_errors: list[str]) -> None:
        self.validation_errors = validation_errors
        super().__init__("; ".join(validation_errors) or "plan generation failed")


class PlanNotFoundError(Exception):
    """Raised when a ref does not resolve to any stored artifact."""


def _applicability_key(plan: DeliveryPhasePlan) -> str:
    event_type = plan.applicability.event_type
    source_system = plan.applicability.source_system
    targets = ".".join(sorted(plan.applicability.selected_targets))
    return f"{event_type}.{source_system}.{targets}"


class PlanStore:
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def _path(self, kind: str, key: str) -> Path:
        return self._base / kind / f"{key}.json"

    def _write(self, kind: str, key: str, record: dict[str, Any]) -> str:
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2))
        return f"{kind}:{key}"

    def store_plan(self, plan: DeliveryPhasePlan) -> str:
        """Persist a successful plan artifact; returns ``"plan:<key>"``."""
        key = _applicability_key(plan)
        return self._write(
            "plan", key, {"status": "succeeded", "artifact": plan.model_dump(mode="json")}
        )

    def store_failed(self, plan: DeliveryPhasePlan, errors: list[str]) -> str:
        """Persist a failed plan record; returns ``"plan:failed:<key>"``.

        The record is written to the same path as a successful plan so a
        subsequent load_plan raises FailedPlanError (audit trail).
        """
        key = _applicability_key(plan)
        self._write(
            "plan", key, {"status": "failed", "validation_errors": errors}
        )
        return f"plan:failed:{key}"

    def load_plan(self, ref: str) -> DeliveryPhasePlan:
        """Load a successful plan artifact by ref."""
        record = self._read(ref)
        if record.get("status") != "succeeded":
            raise FailedPlanError(record.get("validation_errors", ["plan generation failed"]))
        artifact_data: dict[str, Any] = record["artifact"]
        return DeliveryPhasePlan(**artifact_data)

    def store_invocation_log(self, record: dict[str, Any], key: str) -> str:
        """Persist an invocation log record; returns ``"llmcall:<key>"``."""
        return self._write("llmcall", key, record)

    def _read(self, ref: str) -> dict[str, Any]:
        # refs look like "plan:<key>" or "llmcall:<key>"
        kind, key = ref.split(":", 1)
        path = self._path(kind, key)
        if not path.exists():
            raise PlanNotFoundError(f"artifact not found: {ref}")
        data: dict[str, Any] = json.loads(path.read_text())
        return data
