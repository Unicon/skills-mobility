# SmartResume Adapter Design

Status: Draft
Date: 2026-07-16
Related: [Requirements](../2_requirements/smartresume-adapter.md) · [Delivery Router Service Design](./delivery-router-service.md) · [LearnCard Wallet Adapter Design](./learncard-wallet-adapter.md) · [Mock SmartResume Design](./mock-smartresume.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [SmartResume CredentialConnect API](https://my.smartresume.com/api/v1/docs)

## 1. Overview

The SmartResume Adapter is the Python service boundary responsible for delivering an achievement or credential payload to a learner's SmartResume professional record via the SmartResume CredentialConnect REST API.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/smartresume-adapter/` | Python 3.12 + FastAPI + `httpx` | Authenticate to SmartResume, map the delivery envelope to the `/credentials` OB3 body, POST, and return a normalized result |

SmartResume publishes no SDK. The integration is plain HTTP: OAuth2 `client_credentials` token acquisition followed by a JSON `POST /api/v1/credentials`. That makes this adapter a straightforward Python service — no TypeScript component needed, unlike the LearnCard issuer side.

This adapter is the direct sibling of the LearnCard Wallet Adapter in the delivery layer. Both sit behind the Delivery Router. Both own only final-mile binding — the transformation pipeline is responsible for shaping the payload upstream. The adapter maps the orchestrator-delivered payload to the SmartResume request shape, posts it, and normalizes the response.

For **Phase 1**, the Orchestrator still prepares the SmartResume input payload directly. For the **full POC**, that shaping moves upstream into the transformation pipeline; the adapter's internal contract is unchanged in either case.

### Router wiring

The Delivery Router schema enums are extended with:

- `Action.DELIVER_TO_SMARTRESUME = "deliver_to_smartresume"`
- `AdapterKey.SMART_RESUME = "smart_resume"`

The router config gains:

- `DELIVERY_ROUTER_SMARTRESUME_URL` — the SmartResume adapter base URL (e.g. `http://localhost:8920` in local dev).

The router's `adapter_url()` dispatch method maps `AdapterKey.SMART_RESUME` to that URL, matching the existing pattern for `learncard_issuer` and `learncard_wallet`.

## 2. Invocation Model

Recommended endpoint:

```text
POST /internal/deliver-to-smartresume
```

Recommended request shape:

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_smartresume",
  "correlation_id": "corr_123",
  "delivery_config_ref": "smartresume-mock",
  "payload": {
    "recipient": {
      "id": "mailto:learner@example.com",
      "givenName": "Ada",
      "familyName": "Lovelace",
      "email": "learner@example.com"
    },
    "recipienttoken": "<optional>",
    "credentials": [
      {
        "id": "https://example.com/credentials/abc123",
        "type": ["VerifiableCredential", "OpenBadgeCredential"],
        "name": "Introduction to Finance",
        "credentialSubject": {
          "id": "mailto:learner@example.com",
          "achievement": {
            "id": "https://example.com/achievements/finc106",
            "achievementType": "Course",
            "name": "Introduction to Finance",
            "description": "Demonstrates mastery of core finance principles."
          }
        },
        "issuer": {
          "id": "https://example.com/issuers/wasatch",
          "name": "Wasatch University"
        },
        "proof": {
          "type": "DataIntegrityProof",
          "cryptosuite": "eddsa-rdfc-2022",
          "proofValue": "<base58btc-encoded signature>"
        }
      }
    ]
  }
}
```

The `proof` field is present in this example because Finance-routed credentials are issued and signed by `issue_learncard_badge` before reaching SmartResume. The adapter passes `proof` through verbatim. If an incoming credential ever arrives without a `proof`, the adapter omits it and SmartResume accepts the result as an unverified achievement record — this is retained only because SmartResume's API supports it, not because any current POC path produces a no-proof payload (`issue_learncard_badge` signs every delivery).

Recommended response shape:

```json
{
  "status": "succeeded",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_smartresume",
  "correlation_id": "corr_123",
  "external_reference_id": "https://my.smartresume.com/createmyresume/<identifier_token>",
  "result": {
    "redirect_url": "https://my.smartresume.com/createmyresume/<identifier_token>"
  },
  "error": null
}
```

On failure, `status` is `"failed"`, `result` is `null`, and `error` carries the HTTP status code and any SmartResume error body:

```json
{
  "status": "failed",
  "error": {
    "http_status": 401,
    "message": "Unauthorized",
    "body": {}
  }
}
```

The Delivery Router receives this adapter response and folds it into its own normalized `DeliveryActionResponse` envelope before returning to the Orchestrator.

### SmartResume API calls

**Token acquisition:**

```text
POST /api/v1/token
Authorization: Basic <base64(ClientID:AccessKey)>
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials&scope=delete+readonly+replace
```

Response: `{ "access_token": "...", "expires_in": 3600, ... }`

**Achievement delivery:**

```text
POST /api/v1/credentials
Authorization: Bearer <access_token>
Content-Type: application/json

{ "@context": [...], "recipient": {...}, "credentials": [...] }
```

Success response: `{ "redirect_url": "https://my.smartresume.com/createmyresume/<identifier_token>" }`

Error responses use HTTP status codes 400 / 401 / 403 / 405 / 500 with an `application/json` body.

## 3. Modules

- `api/` — internal delivery endpoint (`POST /internal/deliver-to-smartresume`)
- `schemas/` — request and response models for the adapter-facing contract
- `delivery/` — performs the SmartResume token acquisition and `/credentials` POST; owns the mapping from adapter request payload to SmartResume body
- `config/` — service settings (`SMARTRESUME_ADAPTER_` prefix): port, log level, API base URL, `ClientID`, `AccessKey`
- `resultmap/` — normalize SmartResume responses and errors into the adapter response shape

The adapter does not contain routing logic or business-policy evaluation. The `delivery/` module is the only place where SmartResume-specific body construction lives.

> **Implementation scope note — `catalogs/targets/smart_resume/`:** The Field Mapping service currently has target catalogs only for `learncard_issuer/` and `learncard_wallet/`. Authoring `catalogs/targets/smart_resume/` is part of implementing this adapter — it is not an assumed prerequisite that already exists. This new catalog should be built after (or alongside) [#104](https://github.com/Unicon/skills-mobility/issues/104), which makes the `issuer_payload` OBv3 achievement shape conformant and adds the `achievementType`/`alignment` fields SmartResume requires. Building the catalog on top of a complete `issuer_payload` shape avoids re-deriving achievement fields that #104 already standardizes.

## 4. Execution Flow

1. Receive the delivery request from the Delivery Router.
2. Validate the required contract fields; return 422 on missing required fields.
3. Resolve the SmartResume credentials (`ClientID`, `AccessKey`) and API base URL from config.
4. Acquire an OAuth2 access token via `POST /api/v1/token` using HTTP Basic auth. If optional in-memory caching is implemented, check for a valid cached token first (unexpired within its 60-minute lifetime) and skip acquisition on cache hit.
5. Assemble the SmartResume request body:
   - Set `@context` to the standard VC context array.
   - Populate `recipient` from the incoming payload's recipient fields.
   - Forward `recipienttoken` if present.
   - For each credential in the payload: copy `id`, `type`, `name`, `credentialSubject` (including `achievement`), and `issuer`. Include `proof` only if present in the incoming payload. Truncate `alignment[].targetName` to 40 characters and log a warning if truncation occurs.
6. `POST /api/v1/credentials` with `Authorization: Bearer <token>` and the assembled body.
7. On HTTP 200: extract `redirect_url` from the response and normalize into a success result; the `redirect_url` is the `external_reference_id`.
8. On error: normalize the HTTP status code and response body into a structured error result.
9. Return the normalized result to the Delivery Router.

If Step 5 starts doing substantial field generation or schema translation, that is a boundary smell. The upstream transformation pipeline should be producing a nearly-final payload; the adapter's mapping at Step 5 should be mechanical (field copy, format enforcement, proof pass-through).

## 5. Token Caching

For the POC, the simplest correct behavior is to acquire a fresh token per delivery request (no caching). A single delivery operation is infrequent enough that the extra round-trip to `/api/v1/token` is acceptable.

If token caching is added as an optimization: store the token string and its expiry timestamp in a module-level variable (process-scope). Before each delivery, check whether the stored token is present and has more than a small buffer (e.g. 30 seconds) remaining on its 60-minute lifetime. If so, reuse it. Otherwise, acquire a new token and update the store.

Lambda cold-start behavior means cached tokens do not survive function restarts; this is acceptable for the POC.

## 6. Deployment Shape

The expected initial shape is a Python internal service or Lambda-sized component aligned with the repo's Python-first architecture.

### Local Development

| Concern | AWS | Local |
|---|---|---|
| Runtime | Lambda or container | `uvicorn` serving the FastAPI endpoint |
| Secrets | Secrets Manager / SSM Parameter Store | `.env` file (gitignored; `.env.example` committed) |
| SmartResume API | Mock SmartResume (AWS-deployed; see [Mock SmartResume Design](./mock-smartresume.md)) | Mock SmartResume at `http://localhost:8930` (no real creds needed) |

Accessing the real SmartResume staging environment requires a vendor partnership the project does not have; it is out of scope for this POC. Both local and AWS deployments therefore point at Mock SmartResume.

**Port:** `8920` — outside Consul's reserved range (8300–8302, 8500, 8600) and clear of the other POC services (mock-lms 8000, orchestrator 8400, delivery-router 8800, learncard-wallet-adapter 8900, learncard-issuer-adapter 8910).

`SMARTRESUME_ADAPTER_API_URL` must be set explicitly in all environments — there is no single universally correct default:

- **Local:** `http://localhost:8930` (Mock SmartResume running locally)
- **AWS:** the URL of the AWS-deployed Mock SmartResume (set in the Lambda/container environment via Secrets Manager or SSM)

### Configuration Inputs

All resolved from environment (`.env` locally; Secrets Manager in AWS):

| Variable | Description |
|---|---|
| `SMARTRESUME_ADAPTER_PORT` | HTTP port (default: `8920`) |
| `SMARTRESUME_ADAPTER_LOG_LEVEL` | Root log level (default: `INFO`) |
| `SMARTRESUME_ADAPTER_API_URL` | SmartResume base URL — **no default**; must be set explicitly. Local: `http://localhost:8930` (Mock SmartResume). AWS: URL of the AWS-deployed Mock SmartResume. |
| `SMARTRESUME_ADAPTER_CLIENT_ID` | OAuth2 `ClientID` — must match Mock SmartResume's configured `MOCK_SMARTRESUME_CLIENT_ID` (demo default `mock-client-id`); real creds required only if a live SmartResume environment is ever reachable |
| `SMARTRESUME_ADAPTER_ACCESS_KEY` | OAuth2 `AccessKey` — must match Mock SmartResume's `MOCK_SMARTRESUME_ACCESS_KEY` (demo default `mock-access-key`) |

`.env.example` is committed; `.env` is gitignored.

## 7. Testing

- Unit tests around request validation, body assembly (verified vs. unverified cases, `targetName` truncation), and result normalization
- Contract tests that verify the router-facing request/response shape
- Integration tests against a fake/replay HTTP client — no live SmartResume required for routine test runs

**Test approach for the SmartResume HTTP boundary:** inject a fake `httpx` transport (via `httpx.MockTransport` or `respx`) that records requests and returns canned SmartResume responses. Tests assert on the assembled request body (correct `proof` presence/absence, `targetName` length enforcement, `@context` format) and on the normalized response shape. Canned responses should cover: 200 success, 400 bad request, 401 unauthorized, 500 server error.

**Optional end-to-end tests:** supply `SMARTRESUME_ADAPTER_API_URL` pointing at a running Mock SmartResume instance to run the full adapter-to-mock round-trip. These are opt-in and excluded from the standard `pytest` run via a marker. Running against a real SmartResume environment is out of scope for this POC (requires vendor partnership).

## 8. Build Order

1. Define the adapter request/response schemas (`schemas/`).
2. Implement the token acquisition logic and a fake transport for tests.
3. Implement the body assembly and delivery call (`delivery/`), including the verified/unverified `proof` branch and `targetName` truncation.
4. Add the normalized result and error mapping (`resultmap/`).
5. Wire the FastAPI endpoint (`api/`).
6. Wire the adapter to the Delivery Router: add `Action.DELIVER_TO_SMARTRESUME`, `AdapterKey.SMART_RESUME`, `DELIVERY_ROUTER_SMARTRESUME_URL`, and the dispatch entry in `adapter_url()`.
7. Validate against the Mock SmartResume end-to-end (see [Mock SmartResume Design](./mock-smartresume.md) build order).
