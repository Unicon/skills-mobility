# learncard-wallet-adapter

The Python service boundary for **wallet delivery** into LearnCard, after
issuance and profile resolution have already happened upstream. It takes an
already-issued (signed) credential plus the recipient's resolved LearnCard
`profileId` and delivers it via `POST /credential/send/{profileId}` on the
LearnCloud Network API.

See [design](../../docs/3_design/learncard-wallet-adapter.md).

## Endpoint

`POST /internal/deliver-to-learncard-wallet`

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_wallet",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": {
    "recipient_profile_id": "smi-learner-1",
    "signed_credential": { }
  }
}
```

Success → `{"status": "succeeded", "external_reference_id": "<credential URI>", "result": {"delivery_state": "accepted"}, "error": null}`.
A LearnCard error is normalized to `{"status": "failed", ..., "error": {"message": "..."}}` (still HTTP 200 — the router always gets the adapter contract).

A missing `recipient_profile_id` is rejected with **422** — resolving it is the
upstream Profile Resolver's job, not this adapter's.

## Run

```bash
uv sync --all-packages
cp services/learncard-wallet-adapter/.env.example services/learncard-wallet-adapter/.env
# set LEARNCARD_API_TOKEN from tools/learncard-demo's generated .env (ADR-0020, PR #54)
uv run learncard-wallet-adapter          # http://127.0.0.1:8900 — Swagger at /docs
```

`.env` is read regardless of the directory you launch from (it's anchored to the service package), so the token is picked up even when run from the repo root.

Smoke test:

```bash
curl -s localhost:8900/healthz
```

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `LEARNCARD_WALLET_ADAPTER_PORT` | `8900` | Local HTTP port (outside Consul's 8300-8302/8500/8600) |
| `LEARNCARD_WALLET_ADAPTER_LOG_LEVEL` | `INFO` | Root log level |
| `LEARNCARD_API_URL` | `https://network.learncard.com/api` | LearnCloud Network REST base (`libs/learncard-api`) |
| `LEARNCARD_API_TOKEN` | `""` | Pre-minted scoped bearer JWT — from `tools/learncard-demo` (ADR-0020, PR #54) |

## Test

```bash
uv run pytest services/learncard-wallet-adapter
```

Tests use `httpx.MockTransport` — no live LearnCard access required.
