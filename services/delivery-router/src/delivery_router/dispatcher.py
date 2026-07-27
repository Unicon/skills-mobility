"""Action-to-adapter dispatch (design §5). Routes by ``action`` (authoritative),
forwards the envelope to the adapter, and normalizes the adapter's response into
the router's common result shape.
"""

from __future__ import annotations

from typing import Any, Literal

from delivery_router.clients import AdapterClient
from delivery_router.config import Settings
from delivery_router.schemas import (
    Action,
    AdapterKey,
    DeliveryActionRequest,
    DeliveryActionResponse,
)

# action -> (adapter, adapter endpoint path). Phase 1: issuer + wallet (design §6);
# plus SmartResume delivery of the issued (signed) credential for Finance-routed
# events — verified delivery is the primary case (smartresume-adapter reqs §1).
ACTION_ROUTES: dict[Action, tuple[AdapterKey, str]] = {
    Action.ISSUE_LEARNCARD_BADGE: (AdapterKey.LEARNCARD_ISSUER, "/internal/issue-learncard-badge"),
    Action.DELIVER_TO_LEARNCARD_WALLET: (
        AdapterKey.LEARNCARD_WALLET,
        "/internal/deliver-to-learncard-wallet",
    ),
    Action.DELIVER_TO_SMARTRESUME: (
        AdapterKey.SMART_RESUME,
        "/internal/deliver-to-smartresume",
    ),
}


def _adapter_request(req: DeliveryActionRequest) -> dict[str, Any]:
    """The envelope forwarded to the adapter — the router's own routing fields
    (`action`, `adapter_key`) are dropped."""
    return {
        "contract_version": req.contract_version,
        "workflow_id": req.workflow_id,
        "execution_id": req.execution_id,
        "step_id": req.step_id,
        "correlation_id": req.correlation_id,
        "delivery_config_ref": req.delivery_config_ref,
        "payload": req.payload,
    }


def _failed(
    adapter_key: AdapterKey, action: Action, error: dict[str, Any]
) -> DeliveryActionResponse:
    return DeliveryActionResponse(
        status="failed", adapter_key=adapter_key, action=action, error=error
    )


def dispatch(
    req: DeliveryActionRequest, settings: Settings, client: AdapterClient
) -> DeliveryActionResponse:
    adapter_key, path = ACTION_ROUTES[req.action]
    base_url = settings.adapter_url(adapter_key)
    if base_url is None:
        return _failed(
            adapter_key,
            req.action,
            {"message": f"no endpoint configured for adapter {adapter_key.value}"},
        )

    body = client.post(base_url.rstrip("/") + path, _adapter_request(req))

    # Adapters return a normalized shape (status/external_reference_id/result/error);
    # the router passes it through and stamps the resolved adapter + action.
    status: Literal["succeeded", "failed"] = (
        "succeeded" if body.get("status") == "succeeded" else "failed"
    )
    return DeliveryActionResponse(
        status=status,
        adapter_key=adapter_key,
        action=req.action,
        external_reference_id=body.get("external_reference_id"),
        result=body.get("result"),
        error=body.get("error"),
    )
