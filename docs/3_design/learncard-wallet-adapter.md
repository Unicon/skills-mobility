# LearnCard Wallet Adapter Design

Status: Draft
Date: 2026-06-22
Related: [Requirements](../2_requirements/learncard-wallet-adapter.md) · [Delivery Router Service Design](./delivery-router-service.md) · [LearnCard Issuer Adapter Design](./learncard-issuer-adapter.md) · [LearnCard Profile Resolver Design](./learncard-profile-resolver.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard tutorial: Create a Credential](https://docs.learncard.com/tutorials/create-a-credential) · [LearnCard guide: Send Credentials](https://docs.learncard.com/how-to-guides/send-credentials) · [LearnCloud Network API: Credentials](https://docs.learncard.com/sdks/learncard-network/credentials) · [LearnCloud Network API: Authentication](https://docs.learncard.com/sdks/learncard-network/authentication) · [LearnCard guide: Generate API Tokens](https://docs.learncard.com/how-to-guides/deploy-infrastructure/generate-api-tokens) · [LearnCard core concept: Auth Grants and API Tokens](https://docs.learncard.com/core-concepts/architecture-and-principles/auth-grants-and-api-tokens)

## 1. Overview

The LearnCard Wallet Adapter is the Python service boundary responsible for wallet delivery into LearnCard after issuance has already completed.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/learncard-wallet-adapter/` | Python 3.12 + FastAPI + HTTP client | Deliver an already-issued credential to LearnCard wallet APIs |

This design assumes the LearnCard wallet flow is sufficiently supported by direct API calls from Python. If that assumption proves false, the adapter design should be revisited explicitly rather than quietly taking on a second SDK-heavy implementation path.

For **Phase 1**, the Orchestrator still prepares the wallet-input payload directly after issuer response. For the **full POC**, that shaping responsibility is expected to move upstream into the transformation pipeline.

The current official LearnCard docs are relevant here for three reasons:

- the tutorial sends a signed VC with `learnCardIssuer.invoke.sendCredential(recipientProfileId, signedVc)`,
- and the newer "Send Credentials" guide recommends a higher-level `send(...)` method that can issue, sign, and deliver in one call.
- the LearnCloud Network API credentials reference documents `POST /credential/send/{profileId}` as a direct API endpoint for sending a credential to a user by LearnCard `profileId`.

The LearnCloud Network API authentication docs add one more important detail: for REST endpoint usage, LearnCard recommends authenticating with a **scoped API token**, while direct challenge-based DID authentication is available but more complex.

This project intentionally keeps wallet delivery as a separate internal action even though LearnCard exposes simpler combined flows. That separation serves auditability, router stability, and future non-LearnCard issuer/wallet support.

The AuthGrant → API token → bearer token acquisition flow is shared with the LearnCard Profile Resolver through a common `libs/learncard-api` Python package. The credential-delivery endpoint client is service-specific.

### Recipient Profile Resolution

The `POST /credential/send/{profileId}` delivery endpoint requires a LearnCard `profileId`. Resolution of that identifier from upstream learner data (email address, LMS user ID, or similar) is owned by the **LearnCard Profile Resolver** ([design](./learncard-profile-resolver.md)), a standalone Lambda that the Orchestrator invokes as a named plan step before any LearnCard delivery action.

The `recipient_profile_id` field in the adapter request (Section 2) is expected to be present and already resolved when this adapter is invoked. An absent `recipient_profile_id` is an upstream planning error, not a condition this adapter handles by performing its own resolution.

## 2. Invocation Model

Recommended endpoint:

```text
POST /internal/deliver-to-learncard-wallet
```

Recommended request shape:

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_wallet",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": {
    "recipient_profile_id": "@recipient-profile",
    "signed_credential": {}
  }
}
```

Recommended response shape:

```json
{
  "status": "succeeded",
  "external_reference_id": "ext_456",
  "result": {
    "delivery_state": "accepted"
  },
  "error": null
}
```

The router remains responsible for the outer delivery-action envelope. The wallet adapter owns only this adapter-specific contract.

The request payload should therefore contain the already-issued credential plus the LearnCard recipient identifier needed for the adopted delivery flow. When that identifier is a LearnCard Profile ID, it should be treated as case-sensitive, consistent with the official tutorial. That recipient profile is the learner's LearnCard identity, not the issuer's service profile.

The current most-specific documented target for this adapter is:

```text
POST /credential/send/{profileId}
Authorization: Bearer <token>
Body: { "credential": ... }
```

That endpoint comes from LearnCard's LearnCloud Network API credentials reference.

The current most-specific documented auth path for this adapter is:

1. create an AuthGrant,
2. generate an API token from that AuthGrant,
3. call the REST endpoint with `Authorization: Bearer <token>`.

The AuthGrant docs define scopes with the pattern `{resource}:{action}` and list `credential` as a resource with `write` as an available action. Inference: `credential:write` is the likely least-privilege scope for this adapter, but the docs reviewed here do not explicitly tie that exact route to that exact scope.

## 3. Modules

- `api/` — internal wallet-delivery endpoint
- `schemas/` — request and response models
- `learncard_api/` — thin client for the LearnCloud Network API delivery path the project adopts; uses bearer-token auth supplied by `libs/learncard-api`
- `config/` — environment/config resolution for API base URLs; bearer-token acquisition is delegated to `libs/learncard-api`
- `resultmap/` — normalize LearnCard API responses and errors

The adapter should not contain generic routing logic or business-policy evaluation.

## 4. Shared Library: libs/learncard-api

Both the LearnCard Wallet Adapter and the LearnCard Profile Resolver authenticate to LearnCard REST endpoints using a scoped API token derived from an AuthGrant. Rather than duplicate that acquisition logic in two services, it is extracted into a shared Python library at `libs/learncard-api/`.

**What the library owns:**

- Acquiring a scoped API token from the LearnCard AuthGrant → API token flow
- Returning that token to the caller for use as `Authorization: Bearer <token>`
- Loading the AuthGrant credentials and LearnCard API base URL from the supplied delivery configuration

**What the library does not own:**

- HTTP clients for specific LearnCard endpoints (credential send, Search Profiles, Create Profile) — those are service-specific
- Profile resolution, credential issuance, or delivery logic

**Expected interface:**

```python
from learncard_api import LearnCardTokenProvider

provider = LearnCardTokenProvider.from_config(config)
token = provider.get_token(scope="credential:write")
# caller attaches: Authorization: Bearer {token}
```

The required scope differs per service. This adapter is expected to need `credential:write`; the Profile Resolver needs a profiles-related scope. Both scopes need verification against the live LearnCard API before the clients are built.

**Configuration inputs:**

- AuthGrant credentials (from Secrets Manager in AWS; `.env` locally)
- LearnCard API base URL
- Requested scope

**Expected path:** `libs/learncard-api/`

This library must be implemented before this adapter reaches its API client steps (build order step 4). See also [LearnCard Profile Resolver Design](./learncard-profile-resolver.md) for the canonical description of this library.

## 5. Execution Flow

1. Receive the wallet-delivery request from the Delivery Router.
2. Validate the required contract fields.
3. Assert that `recipient_profile_id` is present in the request payload; this must have been resolved by the upstream `resolve_learncard_profile` orchestration step before any delivery dispatch.
4. Resolve the LearnCard configuration referenced by `delivery_config_ref`.
5. Resolve the AuthGrant/API-token configuration used for this adapter, unless a later accepted design replaces the REST token flow with another documented LearnCard auth path.
6. Target the currently documented post-issuance API path, `POST /credential/send/{profileId}`, unless later implementation evidence requires a different documented LearnCard delivery flow.
7. Apply any minor final request-envelope or parameter adjustments required by that API contract, including `Authorization: Bearer <token>` and the expected `credential` request body.
8. Execute the delivery call and preserve the sent credential URI, delivery identifier, or equivalent external reference when present.
9. Normalize the response into the adapter response shape.
10. Return the normalized delivery result to the router.

If Step 6 starts doing substantial field mapping or schema translation, that is a boundary smell and the transformation pipeline should be revisited instead.

If Step 5 reveals that the required LearnCard delivery behavior is not actually usable through the documented API and is available only through the Node/TypeScript SDK, the team should revisit the Python implementation assumption rather than hide a major technology change inside this adapter.

## 6. Deployment Shape

The expected initial shape is a Python internal service or Lambda-sized component aligned with the repo's Python-first architecture.

This adapter remains a separate component boundary from the issuer adapter even though both target LearnCard, because credential issuance and wallet delivery are different vendor operations and use different implementation mechanisms.

### Local Development

| Concern | AWS | Local |
|---|---|---|
| Runtime | Lambda or container | `uvicorn` serving the FastAPI endpoint (no change — the service is already FastAPI) |
| Secrets | Secrets Manager / SSM Parameter Store | `.env` file (gitignored; `.env.example` committed) |
| LearnCard API | Production or staging environment | LearnCard dev environment (no local mock needed) |

No store dependency means no additional local infrastructure is needed beyond the `.env` file.

## 7. Testing

- Unit tests around request validation, API-client behavior, and result normalization
- Contract tests that verify the router-facing request/response shape
- Integration tests against a fake LearnCard wallet API
- Optional live integration tests only when credentials are intentionally supplied

Routine test runs should not require live LearnCard access.

## 8. Build Order

1. Define the adapter request/response schemas.
2. Verify the AuthGrant/API-token flow and confirm the minimum viable scope for this adapter (`credential:write` is likely; verify against the live API).
3. Verify `POST /credential/send/{profileId}` against official docs and a test integration.
4. Implement the Python client using `libs/learncard-api` for bearer-token acquisition. Implement the library first if not already built from Profile Resolver work.
5. Add normalized result and error mapping.
6. Wire the adapter to the Delivery Router.
