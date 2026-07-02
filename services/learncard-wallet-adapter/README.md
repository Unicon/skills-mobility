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

## Read-back (shows delivery)

`GET /internal/delivered-credential?uri=<external_reference_id>`

Read-only proof for the Admin UI ([#53](https://github.com/Unicon/skills-mobility/issues/53), [ADR-0020](../../docs/decisions/0020-no-email-learncard-delivery.md)): using the recipient's `credentials:read` token, it checks whether the credential `uri` (returned by delivery) is present in the recipient wallet's incoming list and resolves the full VC to render.

- Present → `{"delivered": true, "recipient_profile_id": "...", "sent_at": "...", "credential": { }, "error": null}`
- Not present → `{"delivered": false, ...}`
- LearnCard/transport error → `{"delivered": false, "error": "..."}`

No accept/write: a delivered credential sits in `incoming` (pending) until accepted, which is sufficient proof it reached the wallet.

## Run

```bash
uv sync --all-packages
cp services/learncard-wallet-adapter/.env.example services/learncard-wallet-adapter/.env  # set LEARNCARD_API_TOKEN
uv run learncard-wallet-adapter          # http://127.0.0.1:8600 — Swagger at /docs
```

Smoke test:

```bash
curl -s localhost:8600/healthz
```

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `LEARNCARD_WALLET_ADAPTER_PORT` | `8600` | Local HTTP port (clear of Consul's 8300) |
| `LEARNCARD_WALLET_ADAPTER_LOG_LEVEL` | `INFO` | Root log level |
| `LEARNCARD_API_URL` | `https://network.learncard.com/api` | LearnCloud Network REST base (`libs/learncard-api`) |
| `LEARNCARD_API_TOKEN` | `""` | Sender bearer for delivery (`credentials:write`) — from `tools/learncard-demo` |
| `LEARNCARD_RECIPIENT_API_TOKEN` | `""` | Recipient read bearer (`credentials:read`) for the read-back (#53) |

## Test

```bash
uv run pytest services/learncard-wallet-adapter
```

Tests use `httpx.MockTransport` — no live LearnCard access required.
