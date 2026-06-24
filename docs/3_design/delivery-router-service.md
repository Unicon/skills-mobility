# Delivery Router Service Design

Status: Draft
Date: 2026-06-22
Related: [Requirements](../2_requirements/delivery-router-service.md) · [LearnCard Issuer Adapter Design](./learncard-issuer-adapter.md) · [LearnCard Wallet Adapter Design](./learncard-wallet-adapter.md) · [POC Component Boundary Matrix](./poc-component-boundaries.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md)

## 1. Overview

The Delivery Router Service is a thin Python delivery facade between the Orchestrator and target-specific adapters.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/delivery-router/` | Python 3.12 + FastAPI | Validate delivery envelopes, dispatch actions, apply shared delivery mechanics, normalize results |

The router is intentionally not a second transformation layer and not a second orchestrator. It receives a single approved delivery action, executes it against the correct adapter, and returns a normalized result.

In **Phase 1**, the Orchestrator is still the component that prepares the adapter input payloads directly. In the **full POC**, that shaping responsibility is expected to move upstream into the transformation pipeline while the router remains unchanged.

## 2. Recommended Runtime Shape

The simplest useful initial shape is a synchronous internal HTTP/JSON service:

```
Orchestrator
  -> POST /delivery-actions
  -> Delivery Router dispatcher
  -> adapter-specific client
  -> target adapter
  -> normalized result
  -> Orchestrator
```

One router request should correspond to one delivery action invocation. Retry at the router layer should be deterministic and configuration-driven rather than hidden inside vendor-specific adapter code.

## 3. Internal API Contract

Recommended endpoint:

```text
POST /delivery-actions
```

Recommended request shape:

```json
{
  "action": "issue_learncard_badge",
  "contract_version": "v1",
  "adapter_key": "learncard_issuer",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_issuer",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": {}
}
```

Recommended response shape:

```json
{
  "status": "succeeded",
  "adapter_key": "learncard_issuer",
  "action": "issue_learncard_badge",
  "external_reference_id": "ext_123",
  "result": {},
  "error": null
}
```

The response shape should be stable across adapters even when the nested `result` body differs per action.

## 4. Modules

- `api/` — internal delivery endpoint(s)
- `schemas/` — request and normalized response models
- `dispatcher/` — action-to-adapter resolution and dispatch rules
- `clients/` — thin HTTP clients for downstream adapters
- `config/` — adapter bindings, timeout/retry configuration, and delivery config lookup
- `deliverylog/` — standardized delivery-attempt and delivery-result record emission

The router should not contain target-specific field mapping code. Any adapter-specific logic inside `clients/` should be mechanical request assembly only.

### Delivery Config Resolution

The `delivery_config_ref` field in every router request is a logical name (such as `"learncard-dev"`) used to select a named configuration bundle.

The router's `config/` module uses it to resolve the adapter endpoint URL and any behavioral settings (timeout, retry limits) appropriate for that named environment. The ref is also forwarded to the adapter in the request, so the adapter can independently resolve its own vendor credentials (LearnCard seed, AuthGrant credentials, etc.) from the same name without the router needing to know their contents.

Resolution is environment-specific:

- **Local:** named bundles map to entries in a `.env` file.
- **AWS:** they map to named entries in Secrets Manager or SSM Parameter Store.

The router neither stores nor inspects vendor-specific credentials. Its only obligation is to load the adapter endpoint address and delivery mechanics config for the named ref and pass the ref through to the adapter.

## 5. Execution Flow

1. Receive one delivery action request from the Orchestrator.
2. Validate the envelope fields, action, and contract version.
3. Resolve the configured adapter binding for that action.
4. Record a delivery-attempt event or log entry with workflow/execution/step identifiers.
5. Invoke the downstream adapter using a thin client.
6. Normalize the adapter response into the router's common result envelope.
7. Record the delivery result.
8. Return the normalized result to the Orchestrator.

If the downstream adapter fails, the router should preserve structured failure details rather than flattening everything into an opaque error string.

## 6. Phase Split

**Phase 1**

- support `issue_learncard_badge` -> `learncard_issuer`
- support `deliver_to_learncard_wallet` -> `learncard_wallet`
- no SmartResume yet

**Target POC**

- add `deliver_to_smartresume`
- keep the same router-facing envelope while adding new action-specific payload schemas

## 7. Testing

- Unit tests for envelope validation, dispatch rules, timeout/retry policy selection, and result normalization
- API tests for `POST /delivery-actions`
- Integration tests against fake adapter endpoints
- No live vendor dependency in routine tests; adapters should be stubbed or mocked at the router boundary

## 8. Build Order

1. Define the router request/response schemas.
2. Implement dispatch rules for the LearnCard issuer and wallet actions.
3. Add adapter clients and normalized result handling.
4. Add standardized delivery-attempt/result logging.
5. Extend with SmartResume and additional adapters later.
