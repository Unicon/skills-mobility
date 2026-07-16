# smartresume-adapter

The Python service boundary for **SmartResume delivery**, after payload shaping
has already happened upstream. It takes an achievement or credential payload
already shaped for SmartResume, acquires an OAuth2 token, and delivers it via
`POST /api/v1/credentials` on the SmartResume CredentialConnect API.

The primary POC case is a non-credential-enabled course achievement (no `proof`
— SmartResume accepts it as an unverified skill record). An already-issued VC
carrying a `proof` is delivered in the same shape; the `proof` is passed through
verbatim.

See [design](../../docs/3_design/smartresume-adapter.md).

## Endpoint

`POST /internal/deliver-to-smartresume`

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_smartresume",
  "correlation_id": "corr_123",
  "delivery_config_ref": "smartresume-staging",
  "payload": {
    "recipient": { "id": "mailto:learner@example.com", "givenName": "Ada" },
    "credentials": [
      {
        "id": "https://example.com/credentials/abc123",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "credentialSubject": {
          "id": "mailto:learner@example.com",
          "achievement": { "id": "https://example.com/achievements/finc106", "achievementType": "Course" }
        },
        "issuer": { "id": "https://example.com/issuers/wasatch" }
      }
    ]
  }
}
```

Success → `{"status": "succeeded", "external_reference_id": "<redirect_url>", "result": {"redirect_url": "<redirect_url>"}, "error": null}`.
A SmartResume error is normalized to `{"status": "failed", ..., "error": {"message": "...", "http_status": 401, "body": {}}}` (still HTTP 200 — the router always gets the adapter contract).

The adapter sets `@context` to the VC v1 + OBv3 context, forwards `recipienttoken`
only if present, and includes `proof` only when the incoming credential carries
one.

## Run

```bash
uv sync --all-packages
cp services/smartresume-adapter/.env.example services/smartresume-adapter/.env
# point SMARTRESUME_ADAPTER_API_URL at the Mock SmartResume (default) or staging
uv run smartresume-adapter          # http://127.0.0.1:8920 — Swagger at /docs
```

`.env` is read regardless of the directory you launch from (it's anchored to the
service package), so the credentials are picked up even when run from the repo root.

Smoke test:

```bash
curl -s localhost:8920/healthz
```

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `SMARTRESUME_ADAPTER_PORT` | `8920` | Local HTTP port (outside Consul's 8300-8302/8500/8600) |
| `SMARTRESUME_ADAPTER_LOG_LEVEL` | `INFO` | Root log level |
| `SMARTRESUME_ADAPTER_API_URL` | `https://mystage.smartresume.com` | SmartResume base URL (staging, prod, or mock) |
| `SMARTRESUME_ADAPTER_CLIENT_ID` | `""` | OAuth2 `ClientID` (vendor secret) |
| `SMARTRESUME_ADAPTER_ACCESS_KEY` | `""` | OAuth2 `AccessKey` (vendor secret) |

A fresh token is acquired per delivery request (POC-simple; no caching).

## Test

```bash
uv run pytest services/smartresume-adapter
```

Tests use `httpx.MockTransport` — no live SmartResume access required.
