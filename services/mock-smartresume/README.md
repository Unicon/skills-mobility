# mock-smartresume

A deterministic, stateless offline stand-in for the **SmartResume
CredentialConnect API** — the SmartResume equivalent of what the Mock LMS is for
Canvas. It exists so the demo runs with no real SmartResume credentials or
network access.

It implements only the subset the SmartResume Adapter calls:

- `POST /api/v1/token` — OAuth2 `client_credentials` token endpoint (Basic auth
  validated against the configured ClientID/AccessKey; returns a fixed canned token).
- `POST /api/v1/credentials` — credential delivery (requires the canned Bearer
  token; minimally validates the OB3 body; returns a deterministic `redirect_url`).
- `GET /healthz` — health check.

The adapter's code, config, and tests are identical whether it points here or at
the real service — only `SMARTRESUME_ADAPTER_API_URL` differs.

> **This is NOT SmartResume.** No resume is created, nothing is persisted.

See [design](../../docs/3_design/mock-smartresume.md).

## Endpoints

```text
POST /api/v1/token          # Basic auth + grant_type=client_credentials -> {access_token, token_type, expires_in}
POST /api/v1/credentials    # Bearer <canned> + OB3 body -> {redirect_url}
GET  /healthz               # -> {"status": "ok"}
```

The `redirect_url` identifier is `sha256(recipient_id + "|" + first_credential_id)[:16]`,
so the same inputs always produce the same URL. `proof` on a credential is
optional (verified and unverified paths both return 200). The redirect uses a
`.example` domain so mock responses are visually distinguishable in logs.

## Run

```bash
uv sync --all-packages
uv run mock-smartresume          # http://127.0.0.1:8930 — Swagger at /docs
```

Smoke test:

```bash
curl -s localhost:8930/healthz
```

### Sample requests

Both authenticated endpoints, pasteable as-is against the defaults
(`mock-client-id` / `mock-access-key`; the canned token is
`mock-smartresume-token`). Prefer curl over Swagger's "Try it out" for these
two if anything looks off — nullable header parameters have rendered
unreliably there historically (the endpoints now use proper `HTTPBasic` /
`HTTPBearer` security schemes, which give Swagger a working "Authorize"
control).

```bash
# 1. Token exchange (Basic auth + client_credentials form)
curl -s localhost:8930/api/v1/token \
  -u mock-client-id:mock-access-key \
  -d 'grant_type=client_credentials' -d 'scope=delete readonly replace'
# -> {"access_token":"mock-smartresume-token","token_type":"Bearer","expires_in":3600}

# 2. Credential delivery (canned Bearer + minimal OB3 body)
curl -s localhost:8930/api/v1/credentials \
  -H 'Authorization: Bearer mock-smartresume-token' \
  -H 'content-type: application/json' \
  -d '{
        "recipient": {"id": "did:web:example.com:users:learner", "email": "learner@example.com"},
        "credentials": [{
          "id": "urn:poc:credential:demo-1",
          "credentialSubject": {"achievement": {"id": "urn:poc:achievement:ACCY-111-OUT-1"}}
        }]
      }'
# -> {"redirect_url":"https://mock.smartresume.example/createmyresume/<deterministic-16-hex>"}
```

## Config

| Env var | Default | Meaning |
| --- | --- | --- |
| `MOCK_SMARTRESUME_PORT` | `8930` | Local HTTP port (outside Consul's 8300-8302/8500/8600) |
| `MOCK_SMARTRESUME_LOG_LEVEL` | `INFO` | Root log level |

No vendor secrets are needed.

## Test

```bash
uv run pytest services/mock-smartresume
```

All tests use the FastAPI `TestClient` — no running server or network required.
