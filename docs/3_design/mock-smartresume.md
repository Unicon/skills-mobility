# Mock SmartResume Design

Status: Draft
Date: 2026-07-16
Related: [Requirements](../2_requirements/mock-smartresume.md) · [SmartResume Adapter Design](./smartresume-adapter.md) · [SmartResume Adapter Requirements](../2_requirements/smartresume-adapter.md) · [Mock LMS Design](./mock-lms.md) · [ADR-0003](../decisions/0003-programming-language.md) · [SmartResume CredentialConnect API](https://my.smartresume.com/api/v1/docs)

## 1. Overview

The Mock SmartResume is a small, stateless FastAPI service that stands in for the real SmartResume CredentialConnect API during local development and automated testing. It is the demo's offline stand-in — the SmartResume equivalent of what the Mock LMS is for Canvas.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/mock-smartresume/` | Python 3.12 + FastAPI + Pydantic | Implement `/api/v1/token` and `/api/v1/credentials` per the real SmartResume contract; return deterministic canned responses |

### Design goals

- **API-identical to the real service** — the SmartResume Adapter's code is unchanged whether it points at the mock or the real API. `SMARTRESUME_ADAPTER_API_URL` is the only knob.
- **Deterministic** — same inputs produce the same outputs every run, so demos repeat and test assertions are stable.
- **Stateless** — no database, no file storage. Responses are computed from the request body alone. Restarting the service produces no behavioral change.
- **Minimal** — implements only the two endpoints the adapter calls, nothing more.

### Boundaries

This service does not simulate the full SmartResume product. It is not a credential registry, a resume builder, or an account manager. Its only job is to accept the OAuth2 token exchange and the OB3 credential POST that the SmartResume Adapter issues, and respond in the same shape as the real API.

---

## 2. Service Shape

```
services/mock-smartresume/
  src/mock_smartresume/
    app.py          — FastAPI app, route registration
    api/
      token.py      — POST /api/v1/token
      credentials.py — POST /api/v1/credentials
      health.py     — GET /healthz
    schemas.py      — request and response Pydantic models
    config.py       — Settings (MOCK_SMARTRESUME_ prefix)
    token_store.py  — canned token value; deterministic token derivation
  tests/
    test_token.py
    test_credentials.py
    test_health.py
  pyproject.toml
  .env.example
```

### Modules

- `app.py` — creates the FastAPI application and registers the three route groups.
- `api/token.py` — handles `POST /api/v1/token`; parses form body, validates `grant_type`, checks Basic auth header (permissive: any non-empty pair), returns canned `access_token`.
- `api/credentials.py` — handles `POST /api/v1/credentials`; validates Bearer token, validates required body fields, derives the deterministic `redirect_url`, returns it.
- `api/health.py` — handles `GET /healthz`.
- `schemas.py` — Pydantic models for the token response, the credentials request body, and the credentials response. These mirror the real SmartResume API shapes.
- `config.py` — `Settings` with `env_prefix="MOCK_SMARTRESUME_"`: `port` (default 8930), `log_level` (default `INFO`).
- `token_store.py` — the canned access token string (a fixed constant, not randomly generated) and the `derive_redirect_token(recipient_id, credential_id)` function that produces the deterministic identifier in the `redirect_url`.

---

## 3. Endpoint Details

### `POST /api/v1/token`

Accepts `application/x-www-form-urlencoded`. The `Authorization` header carries HTTP Basic auth (`ClientID`:`AccessKey`).

**Validation:**

- If `Authorization` header is absent or not Basic: return `401`.
- If decoded credentials are empty strings: return `401`.
- If `grant_type` form field is absent or not `"client_credentials"`: return `400`.
- Scope is accepted as-is; the mock does not validate scope values.

**Response (200):**

```json
{
  "access_token": "mock-smartresume-token",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

The `access_token` value is a fixed string (`"mock-smartresume-token"` or similar). It is defined as a constant in `token_store.py` so tests can import and assert on it.

---

### `POST /api/v1/credentials`

Accepts `application/json`. Requires `Authorization: Bearer <token>`.

**Validation:**

1. If `Authorization` header is absent or not `Bearer <CANNED_TOKEN>`: return `401`.
2. If `recipient` is absent or `recipient.id` is empty: return `400`.
3. If `credentials` is absent, empty, or any entry lacks `id` or `credentialSubject.achievement.id`: return `400`.
4. `proof` is optional on each credential entry; its presence or absence does not affect validation (both are valid per the real API).

**Deterministic `redirect_url`:**

The identifier token appended to the `redirect_url` is derived from the first credential's `id` and the `recipient.id` in a stable, deterministic way. A simple approach: `sha256(recipient_id + "|" + credential_id)[:16]` (hex prefix). This produces the same output for the same inputs across runs and without shared state.

**Response (200):**

```json
{
  "redirect_url": "https://mock.smartresume.example/createmyresume/<deterministic-token>"
}
```

The base URL (`https://mock.smartresume.example/createmyresume/`) is hardcoded in the mock; it intentionally uses a `.example` domain rather than the real SmartResume domain so mock responses are visually distinguishable in logs.

**Error responses** mirror the real SmartResume shapes: `400`, `401`, `405` with `application/json` bodies.

---

### `GET /healthz`

```json
{ "status": "ok" }
```

Always returns `200`. No dependency checks.

---

## 4. Local vs AWS

The Mock SmartResume is **local-only**. It is not deployed to AWS; there is nothing to mock in production because the real SmartResume staging environment is used there.

| Concern | AWS | Local |
|---|---|---|
| Runtime | Not deployed | `uvicorn` serving the FastAPI app |
| Credentials | N/A | None required — any non-empty `ClientID`/`AccessKey` pair works |
| Persistence | N/A | None — stateless |

**Port:** `8930` — outside Consul's reserved range (8300–8302, 8500, 8600) and clear of the other POC services (mock-lms 8000, orchestrator 8400, delivery-router 8800, learncard-wallet-adapter 8900, learncard-issuer-adapter 8910, smartresume-adapter 8920).

**Adapter integration:** point `SMARTRESUME_ADAPTER_API_URL=http://localhost:8930` in the SmartResume Adapter's `.env`. No other config changes are needed; the adapter's token acquisition and delivery calls are identical against mock vs real.

---

## 5. Phasing

The Mock SmartResume is built alongside (or immediately before) the SmartResume Adapter. It is not needed for Phase 1 (which excludes SmartResume delivery) but is needed as soon as the adapter is developed and tested.

Because it is stateless and small, the full service is built in one pass — there is no staged phasing within the mock itself.

---

## 6. Testing

The mock's own tests use the FastAPI `TestClient` directly (no running server needed):

- **Token endpoint:** valid Basic auth + correct `grant_type` → 200 with canned token; missing/empty credentials → 401; wrong `grant_type` → 400.
- **Credentials endpoint:** valid Bearer + well-formed body → 200 with deterministic `redirect_url`; missing Bearer → 401; wrong token value → 401; missing `recipient.id` → 400; missing credential `id` → 400; `proof` absent → 200 (unverified path); `proof` present → 200 (verified path).
- **Health:** `GET /healthz` → 200.
- **Unknown routes:** `GET /api/v1/credentials` → 405; `GET /nonexistent` → 404.

All tests are deterministic and require no network access.

---

## 7. Build Order

1. Define `schemas.py` (token request/response, credentials request/response, error shapes).
2. Implement `token_store.py` (canned token constant + `derive_redirect_token` function).
3. Implement the three route handlers (`api/token.py`, `api/credentials.py`, `api/health.py`).
4. Wire `app.py` and `config.py`.
5. Write tests (`test_token.py`, `test_credentials.py`, `test_health.py`).
6. Validate end-to-end: SmartResume Adapter pointing at the mock, exercising both the unverified (no `proof`) and verified (`proof` present) paths.
