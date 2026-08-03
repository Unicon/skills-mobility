"""DynamoDB mapping store, exercised against moto's in-process DynamoDB fake.

Mirrors the SQLite store's behavioral contract and adds the reason this backend
exists: state written by one store instance is visible to a separate instance
reading the same table (the Lambda cross-invocation case).
"""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from learncard_profile_resolver.store_dynamo import DynamoMappingStore
from moto import mock_aws

TABLE = "profile-mapping-test"
REGION = "us-east-1"


@pytest.fixture
def dynamo(monkeypatch: pytest.MonkeyPatch) -> Iterator[DynamoMappingStore]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    with mock_aws():
        boto3.resource("dynamodb", region_name=REGION).create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield DynamoMappingStore(TABLE, region=REGION)


def test_get_missing_returns_none(dynamo: DynamoMappingStore) -> None:
    assert dynamo.get("email", "nobody@example.edu") is None


def test_put_then_get_roundtrip(dynamo: DynamoMappingStore) -> None:
    dynamo.put("email", "amy@example.edu", "amy-profile", "did:web:users:amy", "directory")

    assert dynamo.get("email", "amy@example.edu") == {
        "profile_id": "amy-profile",
        "did": "did:web:users:amy",
    }
    # Composite key: same value under a different id type is a different mapping.
    assert dynamo.get("student_id", "amy@example.edu") is None


def test_put_upserts_existing_mapping(dynamo: DynamoMappingStore) -> None:
    dynamo.put("email", "amy@example.edu", "old-profile", "did:web:users:old", "directory")
    dynamo.put("email", "amy@example.edu", "new-profile", "did:web:users:new", "manual")

    assert dynamo.get("email", "amy@example.edu") == {
        "profile_id": "new-profile",
        "did": "did:web:users:new",
    }


def test_state_visible_across_store_instances(dynamo: DynamoMappingStore) -> None:
    # The Lambda case: a different instance (new invocation) reads the same table.
    dynamo.put("email", "amy@example.edu", "amy-profile", "did:web:users:amy", "directory")

    other = DynamoMappingStore(TABLE, region=REGION)
    assert other.get("email", "amy@example.edu") == {
        "profile_id": "amy-profile",
        "did": "did:web:users:amy",
    }
