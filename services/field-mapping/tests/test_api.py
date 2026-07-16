from pathlib import Path

from fastapi.testclient import TestClient
from field_mapping.api import create_app
from field_mapping.artifact_store import ArtifactStore
from field_mapping.catalog_store import CatalogStore
from field_mapping.replay_adapter import ReplayAdapter
from field_mapping.service import MappingService

from .conftest import WALLET_BODY

_SEAM_KEYS = {
    "status",
    "mapping_artifact_ref",
    "synthesis_request_ref",
    "requires_synthesis",
    "llm_invocation_log_ref",
    "synthesis_request",
}


def _client(tmp_path: Path) -> TestClient:
    service = MappingService(
        catalog_store=CatalogStore(),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        adapter=ReplayAdapter(),
    )
    return TestClient(create_app(service))


def test_post_map_returns_seam_envelope(tmp_path: Path) -> None:
    resp = _client(tmp_path).post("/map", json=WALLET_BODY)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == _SEAM_KEYS
    assert body["status"] == "succeeded"


def test_post_map_contract_violation_is_422(tmp_path: Path) -> None:
    # credential_template must not carry a delivery_target (§4) -> request validation 422.
    bad = {**WALLET_BODY, "transformation_type": "credential_template"}
    resp = _client(tmp_path).post("/map", json=bad)
    assert resp.status_code == 422
