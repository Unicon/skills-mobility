# LearnCard Profile Resolver Requirements

Status: Draft
Date: 2026-06-22
Related: [Requirements overview](./README.md) · [Delivery Router Service](./delivery-router-service.md) · [LearnCard Issuer Adapter](./learncard-issuer-adapter.md) · [LearnCard Wallet Adapter](./learncard-wallet-adapter.md) · [Design](../3_design/learncard-profile-resolver.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0011](../decisions/0011-orchestration-runtime-technology.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard network profiles](https://docs.learncard.com/sdks/learncard-network/profiles) · [LearnCard Search Profiles](https://docs.learncard.com/sdks/learncard-network/profiles#get-search-profiles-input)

## 1. Purpose

The **LearnCard Profile Resolver** is a standalone Lambda invoked by the Orchestrator as a named plan step before any LearnCard issuance or wallet delivery action.

Both the LearnCard Issuer Adapter and the LearnCard Wallet Adapter require a resolved LearnCard `profileId` before they can operate: the Issuer Adapter needs the recipient's LearnCard-derived DID to embed in `credentialSubject.id`, and the Wallet Adapter needs the `profileId` to target `POST /credential/send/{profileId}`. The Profile Resolver eliminates this shared dependency by resolving it once as a discrete orchestration step, storing the result in the execution context so downstream adapters can consume it without re-resolving.

The incoming learner identifier from the upstream system will typically be an email address or LMS user ID rather than a LearnCard-specific profile handle. The resolver bridges that gap through a three-stage flow: check the resolver's mapping store, search the LearnCard network, and create a profile if no match is found.

## 2. Scope

The LearnCard Profile Resolver serves the orchestration step:

- `resolve_learncard_profile`

For **Phase 1**, this Lambda is required whenever the orchestration plan includes a LearnCard issuance or wallet delivery action and a `profileId` has not already been resolved for the learner.

For the full POC, the resolver remains responsible only for profile resolution. It does not issue credentials, deliver to wallets, or own any downstream delivery logic.

## 3. Input and Output Expectations

The resolver receives an invocation from the Orchestrator containing a learner identifier and standard tracing fields.

At minimum, the invocation contract SHALL include:

- the step type identifier (`resolve_learncard_profile`),
- a learner identifier value (e.g. email address),
- a learner identifier type (to support future identifier types beyond email),
- workflow/execution/step/correlation identifiers, and
- any delivery configuration reference needed to initialize LearnCard API credentials.

The resolver returns a normalized result that includes at minimum:

- success or failure status,
- the resolved LearnCard `profileId` when resolution succeeds,
- the resolved LearnCard DID when available,
- the resolution method (`stored` / `searched` / `created`), and
- structured error information when resolution fails.

## 4. Functional Requirements

- **FR-LPR-1** The LearnCard Profile Resolver SHALL expose an invocable contract for the `resolve_learncard_profile` orchestration step.
- **FR-LPR-2** The LearnCard Profile Resolver SHALL be implemented in Python 3.12.
- **FR-LPR-3** The LearnCard Profile Resolver SHALL validate its required invocation fields before attempting resolution.
- **FR-LPR-4** The LearnCard Profile Resolver SHALL check a persistent mapping store for a previously resolved `profileId` keyed on the learner identifier before making any external LearnCard API calls.
- **FR-LPR-5** The LearnCard Profile Resolver SHALL call the LearnCard Search Profiles API using the learner identifier if no stored mapping exists. **The exact behavior and supported input fields of this endpoint are not yet verified — implementation MUST test this endpoint against a live LearnCard dev environment before depending on it for email-based or identifier-based lookup.**
- **FR-LPR-6** The LearnCard Profile Resolver SHALL call the LearnCard Create Profile API to create a new profile for the learner if no profile is found via the search step.
- **FR-LPR-7** The LearnCard Profile Resolver SHALL persist the resolved or newly created `profileId` and DID in the mapping store so subsequent steps and future invocations can reuse them without re-resolving.
- **FR-LPR-8** The LearnCard Profile Resolver SHALL authenticate to the LearnCard API using a scoped API token obtained from an AuthGrant-based flow, keeping credentials out of source control and committed artifacts.
- **FR-LPR-9** The LearnCard Profile Resolver SHALL return the resolution method alongside the resolved `profileId` so the Orchestrator can distinguish a cached result from a freshly searched or created profile.
- **FR-LPR-10** The LearnCard Profile Resolver SHALL return errors in a structured form that allows the Orchestrator to distinguish failure from success and preserve auditability.
- **FR-LPR-11** The LearnCard Profile Resolver SHALL attach or preserve workflow, execution, step, and correlation identifiers in its logs and result records.
- **FR-LPR-12** The LearnCard Profile Resolver SHALL NOT own credential issuance, wallet delivery, delivery routing, business-policy enforcement, or workflow planning.
- **FR-LPR-13** The LearnCard Profile Resolver SHALL NOT be called by the Delivery Router; it is an Orchestrator-level step that runs before any delivery actions are dispatched.

## 5. Out of Scope

The LearnCard Profile Resolver does not own:

- LearnCard credential issuance,
- LearnCard wallet delivery,
- SmartResume delivery,
- transformation mapping generation,
- delivery target selection,
- policy validation, or
- orchestration decisions.
