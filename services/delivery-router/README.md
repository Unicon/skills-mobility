# delivery-router

The thin delivery facade between the Orchestrator and the target-specific
adapters ([ADR-0016](../../docs/decisions/0016-delivery-routing-topology.md)). It
takes one already-approved delivery action, dispatches it to the correct adapter
over HTTP, applies shared mechanics (timeout, config-driven retry, correlation,
standardized logging), and returns a normalized result.

It is **not** a second orchestrator and **not** a transformation layer — no
target-specific field mapping. See [design](../../docs/3_design/delivery-router-service.md).

## Endpoint

`POST /delivery-actions`

```json
{
  "action": "deliver_to_learncard_wallet",
  "contract_version": "v1",
  "adapter_key": "learncard_wallet",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_wallet",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": { }
}
```

Response (stable across adapters; `result`/`payload` bodies differ per action):

```json
{ "status": "succeeded", "adapter_key": "learncard_wallet", "action": "deliver_to_learncard_wallet",
  "external_reference_id": "lc:network:…", "result": { }, "error": null }
```

Phase-1 actions (design §6): `issue_learncard_badge` → `learncard_issuer`, `deliver_to_learncard_wallet` → `learncard_wallet`.

- The router **routes by `action`** (authoritative) and echoes the resolved `adapter_key`.
- Adapter/transport failures — after config-driven retries on transport errors — normalize to `status: "failed"` with **structured** `error` (HTTP 200); the router never leaks a raw exception or an unconfigured-adapter into an HTTP error.

## Run

```bash
uv sync --all-packages
cp services/delivery-router/.env.example services/delivery-router/.env   # point at running adapters
uv run delivery-router          # http://127.0.0.1:8800 — Swagger at /docs
```

Smoke test: `curl -s localhost:8800/healthz`

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `DELIVERY_ROUTER_PORT` | `8800` | Local HTTP port (clear of Consul's 8300) |
| `DELIVERY_ROUTER_LEARNCARD_ISSUER_URL` | `None` | Issuer adapter base URL |
| `DELIVERY_ROUTER_LEARNCARD_WALLET_URL` | `None` | Wallet adapter base URL |
| `DELIVERY_ROUTER_REQUEST_TIMEOUT` | `30.0` | Per-request timeout (s) |
| `DELIVERY_ROUTER_RETRY_LIMIT` | `1` | Retries on transport errors (on top of the first try) |
| `DELIVERY_ROUTER_LOG_LEVEL` | `INFO` | Root log level |

## Test

```bash
uv run pytest services/delivery-router
```

Tests stub the adapters at the router boundary (`httpx.MockTransport`) — no live vendor dependency.
