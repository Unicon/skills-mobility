# LearnCard Wallet Adapter Requirements

Status: Draft
Date: 2026-06-22
Related: [Requirements overview](./README.md) · [Delivery Router Service](./delivery-router-service.md) · [LearnCard Profile Resolver](./learncard-profile-resolver.md) · [LearnCard Issuer Adapter](./learncard-issuer-adapter.md) · [Design](../3_design/learncard-wallet-adapter.md) · [Phase 1 POC Slice](./phase-1-poc-slice.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard tutorial: Create a Credential](https://docs.learncard.com/tutorials/create-a-credential) · [LearnCard guide: Send Credentials](https://docs.learncard.com/how-to-guides/send-credentials) · [LearnCloud Network API: Credentials](https://docs.learncard.com/sdks/learncard-network/credentials) · [LearnCloud Network API: Authentication](https://docs.learncard.com/sdks/learncard-network/authentication) · [LearnCard guide: Generate API Tokens](https://docs.learncard.com/how-to-guides/deploy-infrastructure/generate-api-tokens) · [LearnCard core concept: Auth Grants and API Tokens](https://docs.learncard.com/core-concepts/architecture-and-principles/auth-grants-and-api-tokens)

## 1. Purpose

The **LearnCard Wallet Adapter** is the vendor-specific adapter that delivers an already-issued credential into the LearnCard wallet flow.

This document assumes the LearnCard wallet-delivery path can be implemented from Python against a sufficiently capable LearnCard API. If that assumption proves false, this component design should be revisited rather than quietly expanded into a second SDK-heavy adapter.

The current official LearnCard docs do **not** present this as a Python flow. They show delivery through SDK methods such as `sendCredential` and recommend a higher-level `send` method for many use cases. They also document a LearnCloud Network API credentials endpoint, `POST /credential/send/{profileId}`, for sending a credential to a user by LearnCard `profileId`. That makes this adapter a reasonable project assumption, but it still needs implementation-time verification against the actual API behavior.

The LearnCard auth docs also make one implementation path clear for REST calls:

- for REST endpoint usage, LearnCard recommends a **scoped API token**,
- that token is created from an **AuthGrant**,
- and the token is presented as `Authorization: Bearer <token>`.

## 2. Scope

The LearnCard Wallet Adapter serves the delivery action:

- `deliver_to_learncard_wallet`

For **Phase 1**, this adapter is required for the LearnCard wallet-delivery step after the LearnCard Issuer Adapter returns the issued credential.

For the full POC, the adapter remains responsible only for LearnCard wallet delivery. It does not issue credentials and it does not own SmartResume delivery.

## 3. Input and Output Expectations

The adapter receives a router-facing wallet-delivery payload that is already prepared upstream for LearnCard wallet delivery.

- In **Phase 1**, the upstream preparation is performed directly by the **Orchestrator** after issuer response.
- In the **full POC**, the payload is expected to be shaped primarily by the transformation pipeline before the adapter is invoked.

At minimum, the invocation contract SHALL include:

- the action name and contract version,
- the issued credential or wallet-delivery payload,
- the recipient LearnCard `profileId` as resolved by the upstream `resolve_learncard_profile` step,
- workflow/execution/step/correlation identifiers, and
- any delivery configuration or credential reference needed to call the LearnCard API.

When the adopted delivery path uses LearnCard Profile IDs, the adapter should treat them as case-sensitive identifiers, consistent with the official LearnCard tutorial. This recipient Profile ID is the learner's LearnCard app identity, not the issuing institution's service profile.

For the current design, the most relevant official API contract is the LearnCloud Network API credentials endpoint:

- `POST /credential/send/{profileId}`
- Bearer token authentication
- request body containing the credential to send

That documented endpoint is the primary reason this project currently believes a Python wallet adapter may be feasible.

For this adapter, the bearer token acquisition flow should be documented as:

1. create an AuthGrant with the required scope,
2. generate an API token from that AuthGrant,
3. send the token as `Authorization: Bearer <token>` when calling the credentials endpoint.

The LearnCard docs define scopes using the pattern `{resource}:{action}` and list `credential` as a resource plus `write` as an action. Inference: the likely least-privilege scope for this adapter is `credential:write`, though the docs reviewed here do not explicitly map that exact endpoint to that exact scope.

The adapter returns a normalized result that includes at minimum:

- success or failure status,
- any sent credential URI, delivery identifier, or comparable external reference LearnCard returns when available,
- delivery-state details if LearnCard exposes them, and
- structured error information when delivery fails.

## 4. Functional Requirements

- **FR-LCW-1** The LearnCard Wallet Adapter SHALL expose a router-facing internal contract for the `deliver_to_learncard_wallet` action.
- **FR-LCW-2** The LearnCard Wallet Adapter SHALL be implemented in Python unless the documented LearnCloud Network API proves insufficient for the required wallet flow.
- **FR-LCW-3** The LearnCard Wallet Adapter SHALL validate its required router-facing payload fields before attempting wallet delivery.
- **FR-LCW-4** The LearnCard Wallet Adapter SHALL accept a recipient `profileId` pre-resolved by the upstream `resolve_learncard_profile` orchestration step (see [LearnCard Profile Resolver](./learncard-profile-resolver.md)).
- **FR-LCW-5** The LearnCard Wallet Adapter SHALL perform only the minimal request-envelope, parameter-binding, or protocol adjustments still required after upstream transformation.
- **FR-LCW-6** The LearnCard Wallet Adapter SHALL target the official post-issuance delivery path documented by LearnCard, currently `POST /credential/send/{profileId}` or a documented successor, and return a normalized result to the Delivery Router.
- **FR-LCW-7** The LearnCard Wallet Adapter SHALL authenticate to the LearnCloud Network API using a scoped API token when calling REST endpoints, unless a later accepted design explicitly adopts a different documented LearnCard authentication path.
- **FR-LCW-8** The LearnCard Wallet Adapter SHALL obtain that API token from an AuthGrant-based flow and SHALL keep the bearer token out of source control and other committed artifacts.
- **FR-LCW-9** The LearnCard Wallet Adapter SHALL preserve any sent credential URI, delivery identifier, or equivalent LearnCard reference returned by the delivery flow.
- **FR-LCW-10** The LearnCard Wallet Adapter SHALL return errors in a structured form that allows the Delivery Router and Orchestrator to distinguish failure from success and preserve auditability.
- **FR-LCW-11** The LearnCard Wallet Adapter SHALL attach or preserve workflow, execution, step, and correlation identifiers in its logs and result records.
- **FR-LCW-12** If implementation verification shows that the documented LearnCard delivery path is only available through the Node/TypeScript SDK rather than a stable Python-callable API, this adapter design SHALL be revisited explicitly.
- **FR-LCW-13** The LearnCard Wallet Adapter SHALL NOT own credential issuance; that remains the responsibility of the LearnCard Issuer Adapter.
- **FR-LCW-14** The LearnCard Wallet Adapter SHALL NOT own delivery target selection, business-policy enforcement, workflow planning, or substantive field mapping.
- **FR-LCW-15** The LearnCard Wallet Adapter SHALL NOT own LearnCard profile lookup or creation; that is the responsibility of the LearnCard Profile Resolver.

## 5. Out of Scope

The LearnCard Wallet Adapter does not own:

- LearnCard credential issuance,
- SmartResume delivery,
- transformation mapping generation,
- synthesized field generation,
- policy validation, or
- orchestration decisions.
