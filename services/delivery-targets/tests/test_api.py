from pathlib import Path
from typing import Any

from delivery_targets.api import create_app
from delivery_targets.artifact_store import ArtifactStore
from delivery_targets.catalog_store import CatalogStore
from delivery_targets.config import Settings
from delivery_targets.replay_adapter import ReplayAdapter
from delivery_targets.service import SelectionService
from fastapi.testclient import TestClient

from .conftest import ACCOUNTING_BODY

_SEAM_KEYS = {
    "status",
    "selection_artifact_ref",
    "selected_targets",
    "llm_invocation_log_ref",
}


def _client(tmp_path: Path) -> TestClient:
    service = SelectionService(
        settings=Settings(mode="replay"),
        catalog_store=CatalogStore(),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        adapter=ReplayAdapter(),
    )
    return TestClient(create_app(service))


def test_post_select_returns_seam_envelope(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/select-delivery-targets", json=ACCOUNTING_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _SEAM_KEYS
    assert body["status"] == "succeeded"
    assert "learncard_issuer" in body["selected_targets"]


def test_post_select_contract_violation_is_422(tmp_path: Path) -> None:
    # Missing required fields -> 422.
    bad: dict[str, Any] = {"execution_id": "exec_1"}
    resp = _client(tmp_path).post("/select-delivery-targets", json=bad)
    assert resp.status_code == 422


def test_healthz_returns_ok(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
