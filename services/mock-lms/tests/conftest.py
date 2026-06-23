import pytest
from fastapi.testclient import TestClient
from mock_lms.app import create_app
from mock_lms.config import Settings


@pytest.fixture
def client() -> TestClient:
    # Explicit local-emitter settings so tests never touch AWS.
    app = create_app(Settings(emitter="local"))
    return TestClient(app)
