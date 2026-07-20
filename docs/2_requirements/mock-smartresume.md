# Mock SmartResume Requirements

Status: Draft
Date: 2026-07-16
Related: [Requirements overview](./README.md) · [SmartResume Adapter Requirements](./smartresume-adapter.md) · [Design](../3_design/mock-smartresume.md) · [Mock LMS APIs](./mock-lms-apis.md) · [ADR-0003](../decisions/0003-programming-language.md) · [SmartResume CredentialConnect API](https://my.smartresume.com/api/v1/docs)

## 1. Purpose

The **Mock SmartResume** is a deterministic stand-in for the real SmartResume CredentialConnect service. It exists so the demo runs offline with no real SmartResume credentials or network access — exactly the role the Mock LMS plays for Canvas.

It implements the subset of the SmartResume API that the SmartResume Adapter uses:

- `POST /api/v1/token` — token endpoint, accepting HTTP Basic auth and returning a canned access token.
- `POST /api/v1/credentials` — credential delivery endpoint, requiring Bearer auth, minimally validating the OB3-shaped request body, and returning a deterministic `redirect_url`.
- `GET /healthz` — health check.

Request and response shapes conform to the real SmartResume CredentialConnect API contract. The SmartResume Adapter's code, configuration, and tests are identical whether it calls the Mock SmartResume or the real service — the only difference is the value of `SMARTRESUME_ADAPTER_API_URL`.

> **This is NOT SmartResume.** No real resume is created. No learner data is persisted beyond the request-response cycle. No account management, resume editing, or CLR/VP/VCALM operations are supported. This is a demo-only offline stand-in.

## 2. Scope

The Mock SmartResume serves the SmartResume Adapter in local development, automated testing, and AWS deployment. Because accessing the real SmartResume staging environment requires a vendor partnership the project does not have, the AWS environment points at Mock SmartResume rather than the real service. The mock is deployed to AWS alongside the other POC services; `SMARTRESUME_ADAPTER_API_URL` points at it in both local and AWS.

It covers only the two endpoints the adapter calls. All other SmartResume CredentialConnect endpoints (`/clr`, `/verifiablepresentation`, `/exchanges/{token}`, and any non-CredentialConnect routes) are out of scope and SHALL return `404` if requested.

## 3. Functional Requirements

### Token endpoint

- **FR-MSR-1** `POST /api/v1/token` SHALL accept HTTP Basic auth (`ClientID`:`AccessKey`).
- **FR-MSR-2** The token endpoint SHALL accept any non-empty `ClientID`/`AccessKey` pair and return a canned access token. Credential validation is deliberately permissive — the goal is offline demo operation, not security.
- **FR-MSR-3** The token endpoint SHALL require `grant_type=client_credentials` in the form body and return `400` if it is absent or set to another value.
- **FR-MSR-4** The token response SHALL conform to the real SmartResume token response shape: `{ "access_token": "<canned token>", "token_type": "Bearer", "expires_in": 3600 }`.
- **FR-MSR-5** The canned token SHALL be a fixed, deterministic string (not a random UUID) so tests can assert on its value.

### Credential delivery endpoint

- **FR-MSR-6** `POST /api/v1/credentials` SHALL require `Authorization: Bearer <token>` and return `401` if the header is absent or the token does not match the value issued by `POST /api/v1/token`.
- **FR-MSR-7** The credentials endpoint SHALL validate that the request body includes a `recipient` object with a non-empty `id` field and at least one entry in `credentials[]`, each with a non-empty `id` and a `credentialSubject.achievement.id`. Return `400` if any required field is missing.
- **FR-MSR-8** The credentials endpoint SHALL accept a `proof` field in a credential entry (verified path) and SHALL accept its absence (unverified path) without error — both are valid per the real API contract.
- **FR-MSR-9** The credentials endpoint SHALL return HTTP 200 with `{ "redirect_url": "https://mock.smartresume.example/createmyresume/<deterministic-token>" }` on success.
- **FR-MSR-10** The `<deterministic-token>` in the `redirect_url` SHALL be derived from the recipient `id` and credential `id` (e.g. a stable hash or a fixed mapping) so the same inputs always produce the same URL. This supports reproducible demo runs and deterministic test assertions.
- **FR-MSR-11** The credentials endpoint SHALL return `405` for any HTTP method other than `POST`.

### Health check

- **FR-MSR-12** `GET /healthz` SHALL return HTTP 200 with `{ "status": "ok" }`. No dependencies to check.

### General

- **FR-MSR-13** All responses SHALL use `Content-Type: application/json`.
- **FR-MSR-14** Unknown routes SHALL return `404`.
- **FR-MSR-15** The service SHALL be stateless between requests. No database, no file storage, no emission bus. Responses are computed from the request alone.
- **FR-MSR-16** The service SHALL be deterministic: the same request always produces the same response, so demo runs are reproducible and test assertions are stable.

## 4. Configuration

All configuration via environment variables with the `MOCK_SMARTRESUME_` prefix.

| Variable | Description | Default |
|---|---|---|
| `MOCK_SMARTRESUME_PORT` | HTTP port | `8930` |
| `MOCK_SMARTRESUME_LOG_LEVEL` | Root log level | `INFO` |

No vendor secrets are needed. The mock accepts any non-empty `ClientID`/`AccessKey` pair at the token endpoint.

## 5. Out of Scope

The Mock SmartResume does not implement:

- Real SmartResume resume creation, learner accounts, or data persistence,
- SmartResume CLR 2.0 (`/clr`), Verifiable Presentation (`/verifiablepresentation`), or VCALM exchange endpoints,
- Token expiry enforcement (the mock does not validate token age),
- Multi-token or multi-session management, or
- Any SmartResume admin, reporting, or account management surfaces.
