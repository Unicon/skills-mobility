# mock-smartresume

A deterministic, stateless offline stand-in for the **SmartResume
CredentialConnect API** — the SmartResume equivalent of what the Mock LMS is for
Canvas. It exists so the demo runs with no real SmartResume credentials or
network access.

It implements only the subset the SmartResume Adapter calls:

- `POST /api/v1/token` — OAuth2 `client_credentials` token endpoint (permissive
  Basic auth; returns a fixed canned token).
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
