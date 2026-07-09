from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from field_mapping.artifact_store import ArtifactStore
from field_mapping.catalog_store import CatalogStore
from field_mapping.contracts import MappingRequest
from field_mapping.replay_adapter import ReplayAdapter
from field_mapping.service import MappingService

# Request bodies whose source_payloads match the committed replay fixtures.
WALLET_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "transformation_type": "wallet_payload",
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "delivery_target": "learncard_wallet",
    "synthesis_allowed": False,
    "source_payloads": {
        "profile_resolution": {"recipient_profile_id": "smi-demo-learner"},
        "issued_badge": {"proof": {"type": "DataIntegrityProof"}},
    },
}

ISSUER_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "transformation_type": "issuer_payload",
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "delivery_target": "learncard_issuer",
    "synthesis_allowed": True,
    "source_payloads": {
        "outcome": {
            "code": "1.0.0",
            "display_name": "Demonstrate the sample competency",
            "description": "Demonstrates mastery of the sample competency.",
        },
        "profile_resolution": {
            "issuer_id": "did:web:issuer.example.com",
            "recipient_did": "did:web:network.learncard.com:users:learner",
        },
    },
}


@pytest.fixture
def wallet_request() -> MappingRequest:
    return MappingRequest(**WALLET_BODY)


@pytest.fixture
def issuer_request() -> MappingRequest:
    return MappingRequest(**ISSUER_BODY)


@pytest.fixture
def artifact_store(tmp_path: Path) -> ArtifactStore:
    return ArtifactStore(tmp_path / "artifacts")


@pytest.fixture
def make_service(artifact_store: ArtifactStore) -> Callable[..., MappingService]:
    def _make(adapter: Any = None, **kwargs: Any) -> MappingService:
        return MappingService(
            catalog_store=CatalogStore(),
            artifact_store=artifact_store,
            adapter=adapter or ReplayAdapter(),  # packaged canonical fixtures
            **kwargs,
        )

    return _make
