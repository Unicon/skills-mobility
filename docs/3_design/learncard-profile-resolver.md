# LearnCard Profile Resolver Design

Status: Draft
Date: 2026-06-22
Related: [Requirements](../2_requirements/learncard-profile-resolver.md) · [Delivery Router Service Design](./delivery-router-service.md) · [LearnCard Issuer Adapter Design](./learncard-issuer-adapter.md) · [LearnCard Wallet Adapter Design](./learncard-wallet-adapter.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard Search Profiles](https://docs.learncard.com/sdks/learncard-network/profiles#get-search-profiles-input)

## 1. Overview

The LearnCard Profile Resolver is a standalone Python Lambda invoked by the Orchestrator as a named plan step before any LearnCard issuance or wallet delivery action.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Lambda | `services/learncard-profile-resolver/` | Python 3.12 + HTTP client | Resolve or create a LearnCard profile from a learner identifier; persist the mapping |

Both the LearnCard Issuer Adapter and the Wallet Adapter require a resolved LearnCard `profileId` before they can operate. Rather than duplicating resolution logic across two services that use different runtimes (TypeScript for the Issuer Adapter, Python for the Wallet Adapter), resolution runs once as a discrete orchestration step. The Orchestrator stores the resolved `profileId` and DID in the execution context; the issuer and wallet steps consume them without re-resolving.

The resolver does not use the LearnCard SDK. All interactions are HTTP calls to the LearnCard REST APIs, authenticated with a scoped bearer token. The shared `libs/learncard-api` package (built in #40) holds + attaches that pre-minted bearer via a common `LearnCardClient`; the profile-endpoint request/response models are service-specific. Token minting itself is a one-time TS/SDK step (see §4).

**Open question — Search Profiles endpoint.** The LearnCard Search Profiles endpoint ([docs](https://docs.learncard.com/sdks/learncard-network/profiles#get-search-profiles-input)) is the linchpin of the resolution flow. Its supported input fields, matching behavior, and result shape are not fully documented. This endpoint must be tested against a live LearnCard dev environment before the resolver can be implemented. The Create Profile endpoint similarly needs verification before the fallback create path is built.

## 2. Invocation Model

The resolver is invoked by the Orchestrator directly, not through the Delivery Router. The Delivery Router handles delivery actions; profile resolution is a prerequisite orchestration step that runs upstream of any delivery dispatch.

Recommended endpoint:

```text
POST /resolve-learncard-profile
```

Recommended request shape:

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_resolve_profile",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": {
    "learner_id_type": "email",
    "learner_id_value": "learner@example.com"
  }
}
```

Recommended response shape:

```json
{
  "status": "succeeded",
  "result": {
    "profile_id": "@learner-handle",
    "did": "did:web:network.learncard.com:users:learner-handle",
    "resolution_method": "stored"
  },
  "error": null
}
```

`resolution_method` values:

| Value | Meaning |
|---|---|
| `stored` | Returned from the resolver's mapping store; no LearnCard API calls made |
| `searched` | Found via the LearnCard Search Profiles endpoint |
| `created` | No match found; a new LearnCard profile was created |

## 3. Modules

- `api/` — resolver endpoint handler
- `schemas/` — request and response models
- `learncard_api/` — thin HTTP client for the Search Profiles and Create Profile endpoints; uses bearer-token auth supplied by `libs/learncard-api`
- `store/` — read/write wrapper for the learner-identifier-to-profileId mapping store
- `config/` — environment/config resolution for API base URLs; bearer-token acquisition is delegated to `libs/learncard-api`
- `resultmap/` — normalize LearnCard API responses and errors

## 4. Shared Library: libs/learncard-api

Both the LearnCard Profile Resolver and the LearnCard Wallet Adapter call LearnCloud Network REST endpoints with a scoped bearer token. Rather than duplicate the auth + transport wiring in two services, it is extracted into a shared Python library at `libs/learncard-api/` (built in #40).

> **Updated after the #39 spike.** Minting a token from a seed is the LearnCard **JS SDK**'s DID-auth challenge/sign flow — not practical to reproduce in Python. So the scoped bearer is minted **once on the TS side** and supplied to this library as config (`LEARNCARD_API_TOKEN`); the library *holds and attaches* it and does not run the AuthGrant flow. See the [#39 findings](https://github.com/Unicon/skills-mobility/issues/39).

**What the library owns:**

- An authenticated `httpx` client (`LearnCardClient`) that attaches `Authorization: Bearer <token>`, targets the configured base URL, and raises on error responses (no silent drops)
- Loading the API base URL + pre-minted scoped bearer from config (`LEARNCARD_API_URL`, `LEARNCARD_API_TOKEN`)

**What the library does not own:**

- Minting/acquiring the token (a one-time TS/SDK setup step)
- Request/response models for specific endpoints (Search/Create Profile, `/send`) — those are service-specific
- Profile resolution, credential issuance, or delivery logic

**Interface:**

```python
from learncard_api import LearnCardClient, LearnCardSettings

with LearnCardClient(LearnCardSettings()) as client:
    client.get("/profile")  # then service-specific Search/Create Profile calls
```

The scope is baked into the pre-minted token rather than requested per call. The Profile Resolver's token needs a profiles-related scope for the Search Profiles and Create Profile endpoints; the Wallet Adapter's needs a send/credential scope. The exact scope strings still warrant a check against the live API before the clients are built.

**Configuration inputs:**

- `LEARNCARD_API_TOKEN` — pre-minted scoped bearer (Secrets Manager in AWS; `.env` locally)
- `LEARNCARD_API_URL` — LearnCloud Network REST base

**Path:** `libs/learncard-api/`

This library must be implemented before the Profile Resolver reaches its API client steps (build order step 6) and before the Wallet Adapter reaches its API client steps (build order step 4 in [LearnCard Wallet Adapter Design](./learncard-wallet-adapter.md)).

## 5. Execution Flow

1. Receive the resolution request from the Orchestrator.
2. Validate the required contract fields, including `learner_id_type` and `learner_id_value`.
3. Query the mapping store for an existing entry keyed on `(learner_id_type, learner_id_value)`. If found, return immediately with `resolution_method: stored`.
4. Resolve the AuthGrant/API-token configuration for LearnCard API access.
5. Call the LearnCard Search Profiles endpoint with the learner identifier. Interpret the result based on what implementation testing reveals about the endpoint's matching behavior and result shape.
6. If a matching profile is found: persist the mapping (`learner_id_type + learner_id_value → profile_id + did`) and return with `resolution_method: searched`.
7. If no profile is found: call the LearnCard Create Profile endpoint to create a new profile for the learner.
8. Persist the newly created `profile_id` and DID in the mapping store.
9. Return the resolved result with `resolution_method: created`.

Steps 5 and 7 cannot be designed in detail until the Search Profiles and Create Profile endpoints are tested against a live environment (see Build Order step 2).

## 6. Mapping Store

For the POC, the expected store is a DynamoDB table owned exclusively by the Profile Resolver.

| Attribute | Role |
|---|---|
| `pk` | Composite key: `{learner_id_type}#{learner_id_value}` |
| `profile_id` | Resolved LearnCard profile handle |
| `did` | Resolved LearnCard DID |
| `resolved_at` | ISO 8601 timestamp of initial resolution |
| `resolution_method` | How the profile was first resolved (`searched` or `created`) |

The Issuer Adapter and Wallet Adapter do not read from this table directly. They consume the resolved `profileId` and DID from the execution context that the Orchestrator populates after the resolver step completes.

## 7. Deployment Shape

The expected deployment shape is a standalone Python Lambda. It sits upstream of the Delivery Router in the Orchestrator's plan — not alongside the delivery adapters and not routed through the Delivery Router.

The key design rule is that the Issuer Adapter (TypeScript) and the Wallet Adapter (Python) must not each duplicate profile resolution logic. Centralizing resolution here eliminates that duplication regardless of how many LearnCard adapters are added later.

### Local Development

| Concern | AWS | Local |
|---|---|---|
| Runtime | Lambda | `uvicorn` serving the FastAPI endpoint |
| Mapping store | DynamoDB table | SQLite (consistent with the project's local-dev convention) |
| Secrets | Secrets Manager / SSM Parameter Store | `.env` file (gitignored; `.env.example` committed) |
| LearnCard API | Production or staging environment | LearnCard dev environment (no local mock needed) |

The `store/` module interface should be pluggable so the DynamoDB and SQLite implementations can be swapped without touching the resolution flow.

## 8. Testing

- Unit tests around request validation, store lookup/write, and result normalization
- Adapter-level tests with the LearnCard API client and mapping store mocked
- Contract tests that verify the Orchestrator-facing request/response shape
- Integration tests that exercise the Search Profiles and Create Profile endpoints against a real LearnCard dev environment — **these must run and findings must be documented before implementation of steps 5–9 of the Execution Flow**

Routine test runs should not require live LearnCard access.

## 9. Build Order

1. Define the resolver request/response schemas.
2. **Test the LearnCard Search Profiles endpoint in a dev environment.** Confirm what input fields it accepts, what it matches on, and what the result shape looks like. Document findings before writing any client code.
3. Test the Create Profile endpoint. Confirm the required input fields and the `profileId`/DID shape returned on creation.
4. Implement the DynamoDB mapping store module and its read/write wrapper.
5. ~~Implement the `libs/learncard-api` token provider.~~ **Done (#40):** the lib provides an authenticated `LearnCardClient` (holds + attaches a pre-minted bearer); token minting is a one-time TS/SDK step, not part of this lib.
6. Implement the LearnCard API client for Search Profiles and Create Profile based on findings from steps 2–3, using `libs/learncard-api`'s `LearnCardClient` for authenticated calls.
7. Implement the resolution flow (store lookup → search → create → persist).
8. Add normalized result and error mapping.
9. Wire the resolver into the Orchestrator as a named plan step type (`resolve_learncard_profile`).
