# LearnCard Issuer Adapter Requirements

Status: Draft
Date: 2026-06-22
Related: [Requirements overview](./README.md) · [Delivery Router Service](./delivery-router-service.md) · [LearnCard Profile Resolver](./learncard-profile-resolver.md) · [LearnCard Wallet Adapter](./learncard-wallet-adapter.md) · [Design](../3_design/learncard-issuer-adapter.md) · [Phase 1 POC Slice](./phase-1-poc-slice.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard tutorial: Create a Credential](https://docs.learncard.com/tutorials/create-a-credential) · [LearnCard guide: Send Credentials](https://docs.learncard.com/how-to-guides/send-credentials)

## 1. Purpose

The **LearnCard Issuer Adapter** is the vendor-specific adapter that issues and signs credentials through LearnCard's TypeScript SDK.

It is intentionally thin. By the time a request reaches this adapter, the payload should already be approved and mostly shaped for the target flow. The adapter's job is to perform the minimal final binding needed for LearnCard SDK calls and return a normalized result.

The official LearnCard tutorial shows a concrete issuance path built around:

- `initLearnCard(...)` with a secure seed and network capability enabled,
- ensuring the issuer has a service profile,
- constructing an unsigned VC payload,
- and calling `learnCardIssuer.invoke.issueCredential(unsignedVc)` to return a signed VC.

This project should align to that documented issuance flow rather than inventing a custom LearnCard integration pattern.

For this project, these LearnCard terms should be read as follows:

- **Seed**: the secure secret material used by LearnCard to derive the issuer's DID and cryptographic keys. In practice, this is part of the issuing institution's sensitive configuration and must be treated like a secret.
- **Issuer service profile**: the LearnCard-network profile associated with the issuer DID so the issuer can participate on the network. In this project, that profile should represent the issuing institution or issuing service identity, not an end learner.
- **Recipient Profile ID**: the case-sensitive LearnCard app profile identifier for the credential recipient. This is a different concept from the issuer's service profile and should not be conflated with it.

## 2. Scope

The LearnCard Issuer Adapter serves the delivery action:

- `issue_learncard_badge`

For **Phase 1**, this adapter is required for the end-to-end `skill_mastered` and `course_completed` happy paths.

For the full POC, the same adapter remains responsible only for LearnCard issuance. Wallet delivery remains a separate adapter boundary.

The official LearnCard docs also show a simpler combined send flow that can both sign and deliver a credential. This project deliberately does **not** use that combined vendor call as its internal boundary, because the POC wants issuance and wallet delivery to remain separate auditable actions.

## 3. Input and Output Expectations

The adapter receives a router-facing issuer payload that is already prepared upstream for LearnCard issuance.

- In **Phase 1**, the upstream preparation is performed directly by the **Orchestrator**.
- In the **full POC**, the payload is expected to be shaped primarily by the transformation pipeline before the adapter is invoked.

At minimum, the invocation contract SHALL include:

- the action name and contract version,
- the issuer payload,
- workflow/execution/step/correlation identifiers, and
- any delivery configuration or credential reference needed to initialize LearnCard.

The adapter returns a normalized result that includes at minimum:

- success or failure status,
- the issued credential or badge artifact when issuance succeeds,
- any external reference or identifier LearnCard returns when available, and
- structured error information when issuance fails.

## 4. Functional Requirements

- **FR-LCI-1** The LearnCard Issuer Adapter SHALL expose a router-facing internal contract for the `issue_learncard_badge` action.
- **FR-LCI-2** The LearnCard Issuer Adapter SHALL be implemented in Node/TypeScript and use the LearnCard SDK rather than a custom Python wrapper.
- **FR-LCI-3** The LearnCard Issuer Adapter SHALL validate its required router-facing payload fields before attempting issuance.
- **FR-LCI-4** The LearnCard Issuer Adapter SHALL initialize the LearnCard SDK from secure issuer configuration, including the seed material required to derive the issuer DID and keys.
- **FR-LCI-5** The LearnCard Issuer Adapter SHALL enable the LearnCard network capabilities required for issuance and downstream LearnCard interaction.
- **FR-LCI-6** The LearnCard Issuer Adapter SHALL ensure the issuer has a LearnCard service profile before attempting issuance. At minimum, this profile setup SHALL be grounded in the LearnCard-documented `PROFILE_ID` and `PROFILE_NAME` concept or an equivalent internal configuration model. In this project, that issuer profile is expected to represent the issuing institution or issuing service identity.
- **FR-LCI-7** The LearnCard Issuer Adapter SHALL perform only the minimal request-envelope, parameter-binding, or SDK-call adjustments still required after upstream transformation.
- **FR-LCI-8** The LearnCard Issuer Adapter SHALL invoke the LearnCard issuance flow, specifically the SDK's documented `issueCredential` capability or its successor, and return the issued/signed credential artifact to the Delivery Router.
- **FR-LCI-9** The LearnCard Issuer Adapter SHALL preserve the LearnCard-issued credential artifact in a form the downstream wallet-delivery step can use without re-issuing or re-signing it.
- **FR-LCI-10** The LearnCard Issuer Adapter SHALL return errors in a structured form that allows the Delivery Router and Orchestrator to distinguish failure from success and preserve auditability.
- **FR-LCI-11** The LearnCard Issuer Adapter SHALL attach or preserve workflow, execution, step, and correlation identifiers in its logs and result records.
- **FR-LCI-12** The LearnCard Issuer Adapter SHALL NOT collapse issuance and wallet delivery into one combined vendor call at the adapter boundary, even though LearnCard documents higher-level send flows that can do both.
- **FR-LCI-13** The LearnCard Issuer Adapter SHALL NOT own delivery target selection, business-policy enforcement, workflow planning, or substantive field mapping.
- **FR-LCI-14** The LearnCard Issuer Adapter SHALL NOT own wallet delivery; that remains the responsibility of the LearnCard Wallet Adapter.
- **FR-LCI-15** The recipient's LearnCard `profileId` and DID SHALL be resolved upstream by the `resolve_learncard_profile` step (see [LearnCard Profile Resolver](./learncard-profile-resolver.md)) before this adapter is invoked. This adapter SHALL NOT perform or re-perform recipient profile resolution.

## 5. Out of Scope

The LearnCard Issuer Adapter does not own:

- SmartResume delivery,
- LearnCard wallet delivery,
- transformation mapping generation,
- synthesized field generation,
- policy validation, or
- orchestration decisions.
