"""DynamoDB-backed mapping store (ADR-0014) — the Lambda deployment target.

The SQLite ``SqliteMappingStore`` keeps state in a file, which does not survive
across Lambda instances. This backend keeps the same ``MappingStore`` shape but
persists to a DynamoDB table, following the orchestrator's ``DynamoExecutionStore``
precedent (ADR-0014 §9).

One item per mapping, addressed by the same composite ``pk`` the SQLite store
uses (``{learner_id_type}#{learner_id_value}``). All attributes are plain
strings, so items are stored natively (no JSON-body indirection needed).
"""

from __future__ import annotations

import boto3

from learncard_profile_resolver.store import _now, _pk


class DynamoMappingStore:
    def __init__(self, table_name: str, region: str | None = None) -> None:
        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def get(self, id_type: str, id_value: str) -> dict[str, str] | None:
        item = self._table.get_item(Key={"pk": _pk(id_type, id_value)}).get("Item")
        if item is None:
            return None
        return {"profile_id": str(item["profile_id"]), "did": str(item["did"])}

    def put(
        self, id_type: str, id_value: str, profile_id: str, did: str, resolution_method: str
    ) -> None:
        self._table.put_item(
            Item={
                "pk": _pk(id_type, id_value),
                "profile_id": profile_id,
                "did": did,
                "resolved_at": _now(),
                "resolution_method": resolution_method,
            }
        )
