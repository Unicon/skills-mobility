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


COURSE_WALLET_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "transformation_type": "wallet_payload",
    "source_system": "mock_lms",
    "fetch_profile_id": "course_completed.v1",
    "delivery_target": "learncard_wallet",
    "synthesis_allowed": False,
    "source_payloads": {
        "profile_resolution": {"recipient_profile_id": "smi-demo-learner"},
        "issued_badge": {"proof": {"type": "DataIntegrityProof"}},
    },
}

COURSE_ISSUER_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "transformation_type": "issuer_payload",
    "source_system": "mock_lms",
    "fetch_profile_id": "course_completed.v1",
    "delivery_target": "learncard_issuer",
    "synthesis_allowed": True,
    "source_payloads": {
        "course": {
            "id": "ACCY-111",
            "name": "Introduction to Accounting",
            "institution": "Wasatch University",
        },
        "profile_resolution": {
            "issuer_id": "did:web:issuer.example.com",
            "recipient_did": "did:web:network.learncard.com:users:learner",
        },
    },
}


SMARTRESUME_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "transformation_type": "wallet_payload",
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "delivery_target": "smart_resume",
    "synthesis_allowed": False,
    "source_payloads": {
        "profile_resolution": {
            "recipient_did": "did:web:network.learncard.com:users:learner"
        },
        "issued_badge": {"id": "urn:uuid:issued-1", "proof": {"type": "DataIntegrityProof"}},
    },
}

COURSE_SMARTRESUME_BODY: dict[str, Any] = {
    **SMARTRESUME_BODY,
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "fetch_profile_id": "course_completed.v1",
}

# credential_template requests must omit delivery_target and carry every
# required alias from the fetch profile (the required_aliases gate applies
# only to this phase).
CT_BODY: dict[str, Any] = {
    "execution_id": "exec_1",
    "event_id": "evt_1",
    "transformation_type": "credential_template",
    "source_system": "mock_lms",
    "fetch_profile_id": "skill_mastered.v1",
    "synthesis_allowed": True,
    "source_payloads": {
        "outcome": {
            "code": "1.0.0",
            "display_name": "Demonstrate the sample competency",
            "description": "Demonstrates mastery of the sample competency.",
        },
        "assignment": {"name": "Sample assignment"},
        "module_context": {"module_name": "Module 1"},
        "canvas_user": {"id": "WU1"},
        "submission": {"score": 9.0},
        "profile_resolution": {"issuer_id": "did:web:issuer.example.com"},
    },
}

COURSE_CT_BODY: dict[str, Any] = {
    "execution_id": "exec_2",
    "event_id": "evt_2",
    "transformation_type": "credential_template",
    "source_system": "mock_lms",
    "fetch_profile_id": "course_completed.v1",
    "synthesis_allowed": True,
    "source_payloads": {
        "course": {
            "id": "ACCY-111",
            "name": "Introduction to Accounting",
            "institution": "Wasatch University",
        },
        "learner_profile": {"id": "WU1"},
        "enrollment": {"state": "active"},
        "assignments": [{"name": "Sample assignment"}],
        "submissions": [{"score": 9.0}],
        "profile_resolution": {"issuer_id": "did:web:issuer.example.com"},
    },
}


@pytest.fixture
def wallet_request() -> MappingRequest:
    return MappingRequest(**WALLET_BODY)


@pytest.fixture
def issuer_request() -> MappingRequest:
    return MappingRequest(**ISSUER_BODY)


@pytest.fixture
def course_wallet_request() -> MappingRequest:
    return MappingRequest(**COURSE_WALLET_BODY)


@pytest.fixture
def course_issuer_request() -> MappingRequest:
    return MappingRequest(**COURSE_ISSUER_BODY)


@pytest.fixture
def smartresume_request() -> MappingRequest:
    return MappingRequest(**SMARTRESUME_BODY)


@pytest.fixture
def course_smartresume_request() -> MappingRequest:
    return MappingRequest(**COURSE_SMARTRESUME_BODY)


@pytest.fixture
def ct_request() -> MappingRequest:
    return MappingRequest(**CT_BODY)


@pytest.fixture
def course_ct_request() -> MappingRequest:
    return MappingRequest(**COURSE_CT_BODY)


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
