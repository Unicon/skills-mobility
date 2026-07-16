from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from field_synthesis.api import create_app
from field_synthesis.artifact_store import ArtifactStore
from field_synthesis.config import Settings
from field_synthesis.replay_adapter import ReplayAdapter
from field_synthesis.service import SynthesisService

from .conftest import OPEN_BADGE_BODY

_SEAM_KEYS = {"status", "synthesis_result_ref", "llm_invocation_log_ref", "values"}


def _client(tmp_path: Path) -> TestClient:
    service = SynthesisService(
        settings=Settings(mode="replay"),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        adapter=ReplayAdapter(),
    )
    return TestClient(create_app(service))


def test_post_synthesize_returns_seam_envelope(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/synthesize-fields", json=OPEN_BADGE_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _SEAM_KEYS
    assert body["status"] == "succeeded"
    assert body["synthesis_result_ref"] is not None
    assert body["llm_invocation_log_ref"] is not None


def test_post_synthesize_contract_violation_is_422(tmp_path: Path) -> None:
    # Missing required fields -> 422.
    bad: dict[str, Any] = {"execution_id": "exec_1"}
    resp = _client(tmp_path).post("/synthesize-fields", json=bad)
    assert resp.status_code == 422


def test_healthz_returns_ok(tmp_path: Path) -> None:
    resp = _client(tmp_path).get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
