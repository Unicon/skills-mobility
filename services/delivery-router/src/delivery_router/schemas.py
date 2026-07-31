"""Router-facing contract (design §3, ADR-0016).

A stable envelope + normalized response across adapters; the nested ``payload``
and ``result`` bodies differ per action but the envelope does not.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel


class Action(StrEnum):
    ISSUE_LEARNCARD_BADGE = "issue_learncard_badge"
    DELIVER_TO_LEARNCARD_WALLET = "deliver_to_learncard_wallet"
    DELIVER_TO_SMARTRESUME = "deliver_to_smartresume"


class AdapterKey(StrEnum):
    LEARNCARD_ISSUER = "learncard_issuer"
    LEARNCARD_WALLET = "learncard_wallet"
    SMART_RESUME = "smart_resume"


class DeliveryActionRequest(BaseModel):
    action: Action
    contract_version: Literal["v1"]
    # Declared by the caller; the router routes by `action` (authoritative) and
    # echoes the resolved adapter back in the response.
    adapter_key: AdapterKey
    workflow_id: str
    execution_id: str
    step_id: str
    correlation_id: str
    delivery_config_ref: str
    payload: dict[str, Any]


class DeliveryActionResponse(BaseModel):
    status: Literal["succeeded", "failed"]
    adapter_key: AdapterKey
    action: Action
    external_reference_id: str | None = None
    result: dict[str, Any] | None = None
    # Structured failure detail preserved from the adapter, or a router-level
    # error — never flattened to an opaque string (design §5).
    error: dict[str, Any] | None = None
