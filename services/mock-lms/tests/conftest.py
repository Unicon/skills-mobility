import pytest
from fastapi.testclient import TestClient
from mock_lms.app import create_app
from mock_lms.config import Settings


@pytest.fixture
def client() -> TestClient:
    # Explicit local-emitter settings so tests never touch AWS. Pin
    # event_consumer_url=None so a developer's local .env can't leak in and make
    # tests fire real requests at a running event-consumer (CWD-safe .env loading
    # now finds a service-dir .env regardless of where pytest runs).
    app = create_app(Settings(emitter="local", event_consumer_url=None))
    return TestClient(app)
