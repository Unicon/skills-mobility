# SmartResume Adapter Requirements

Status: Draft
Date: 2026-07-16
Related: [Requirements overview](./README.md) · [Delivery Router Service](./delivery-router-service.md) · [LearnCard Wallet Adapter](./learncard-wallet-adapter.md) · [Design](../3_design/smartresume-adapter.md) · [Mock SmartResume Requirements](./mock-smartresume.md) · [Phase 1 POC Slice](./phase-1-poc-slice.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [SmartResume CredentialConnect API](https://my.smartresume.com/api/v1/docs)

## 1. Purpose

The **SmartResume Adapter** is the vendor-specific adapter that delivers an achievement or credential payload into the learner's SmartResume professional record via the SmartResume CredentialConnect API.

Its reason to exist is architectural: the Delivery Router dispatches to registered adapters by key (`smart_resume`), so adding SmartResume as a delivery target required no changes to the router — only this adapter. The same pattern governs all current and future delivery targets.

The in-scope POC credential is a Finance course credential that travels the full issuance pipeline (`issue_learncard_badge` runs for every delivery in this POC) before reaching SmartResume. By the time it arrives here it already carries a signed `proof`. **Verified, signed delivery is the primary case.** The adapter also supports the no-proof path — SmartResume's API accepts achievements without proof as unverified skill records. That branch exists only because the API supports it and is retained for a possible future case; no current POC course routes through it, since `issue_learncard_badge` signs every delivery. The `/credentials` endpoint is the same either way; only the presence or absence of a `proof` array distinguishes verified from unverified submissions.

This document assumes the SmartResume CredentialConnect API is callable from Python using standard HTTP client tooling. SmartResume publishes no SDK; the API contract is prose-documented at the URL above and is stable enough to build against.

## 2. Scope

The SmartResume Adapter serves the delivery action:

- `deliver_to_smartresume`

Its AdapterKey is `smart_resume`. This action and key are registered in the Delivery Router alongside the existing LearnCard actions (`deliver_to_learncard_wallet` / `learncard_wallet`, `issue_learncard_badge` / `learncard_issuer`).

The adapter is invoked for any workflow step where the Workflow Actions planner has approved a `deliver_to_smartresume` action. For the full POC, that step fires when the Delivery Targets Decision Service selects the `smart_resume` target.

## 3. Input and Output Expectations

The adapter receives a router-facing delivery payload already prepared upstream for SmartResume delivery.

- In **Phase 1**, the upstream preparation is performed directly by the Orchestrator (consistent with how the LearnCard wallet adapter is handled in Phase 1).
- In the **full POC**, that shaping responsibility moves upstream into the transformation pipeline; the adapter performs only final-mile protocol binding.

At minimum, the invocation contract SHALL include:

- the action name and contract version,
- the achievement or credential payload shaped for SmartResume (see §4 for the required fields),
- recipient identity fields needed to populate the SmartResume `recipient` object: at minimum `id` (the learner's `email` or equivalent globally-unique identifier), plus any available `givenName`, `familyName`, `email`, `phone`, `studentId`, or `signupOrganization` fields,
- an optional `recipienttoken` if a read-back URL scoped to the recipient is needed,
- workflow/execution/step/correlation identifiers, and
- a delivery config reference (`delivery_config_ref`) identifying the named configuration bundle from which the adapter resolves its credentials (`ClientID` and `AccessKey`).

### SmartResume `/credentials` body mapping

The SmartResume `POST /api/v1/credentials` endpoint expects a JSON body conforming to this shape (required fields noted):

```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1"],
  "recipienttoken": "<str — optional, scopes the redirect URL to this recipient>",
  "recipient": {
    "id": "<req — globally unique learner identifier, e.g. email URI>",
    "givenName": "<optional>",
    "familyName": "<optional>",
    "email": "<optional>",
    "phone": "<optional>",
    "studentId": "<optional>",
    "signupOrganization": "<optional>"
  },
  "credentials": [
    {
      "id": "<req>",
      "type": ["VerifiableCredential", "OpenBadgeCredential"],
      "name": "<optional>",
      "credentialSubject": {
        "id": "<req — learner identifier>",
        "achievement": {
          "id": "<req>",
          "achievementType": "<req — e.g. 'Competency', 'Course', 'SkillsAndAbilities'>",
          "name": "<optional>",
          "description": "<optional>",
          "alignment": [
            {
              "targetName": "<req — max 40 chars>",
              "targetDescription": "<optional>",
              "targetType": "Competency"
            }
          ]
        }
      },
      "issuer": {
        "id": "<req>",
        "name": "<optional>"
      },
      "proof": ["<omit for unverified achievements; present for issued VCs>"]
    }
  ]
}
```

**Verified credentials (primary POC case):** the in-scope Finance course credential travels the full issuance pipeline and arrives at this adapter already signed. The `proof` field is present and the adapter SHALL pass it through verbatim.

**Unverified achievements:** SmartResume accepts achievements without proof as unverified skill records, so the adapter SHALL omit the `proof` array when the incoming payload has none. This branch is retained for that possible future case, not because any current POC course routes that way — every current delivery is signed by `issue_learncard_badge` and arrives with a `proof`.

**SkillSync (skills):** when `achievementType` is `"SkillsAndAbilities"`, skills are listed under `credentialSubject.achievement.alignment[]` with `targetName` (max 40 characters), `targetDescription`, and `targetType: "Competency"`. The adapter SHALL enforce the 40-character limit on `targetName` by truncating if necessary and logging a warning.

The adapter returns a normalized result that includes at minimum:

- success or failure status,
- the `redirect_url` returned by SmartResume (`"https://my.smartresume.com/createmyresume/{identifier_token}"`) when delivery succeeds, preserved as the `external_reference_id`,
- structured error information preserving the HTTP status code and any SmartResume error body when delivery fails.

### OAuth2 token acquisition

SmartResume uses OAuth2 `client_credentials` flow:

1. `POST /api/v1/token` with HTTP Basic auth (`ClientID`:`AccessKey`) and form body `grant_type=client_credentials&scope=delete readonly replace`.
2. Response includes `access_token` valid for 60 minutes.
3. Subsequent calls use `Authorization: Bearer <access_token>`.

The adapter SHALL obtain a token before calling `/credentials`. For the POC, optional in-memory token caching within the token's 60-minute lifetime is acceptable but not required. If caching is omitted, the adapter acquires a fresh token per delivery request — straightforward and correct. If caching is added, the implementation SHALL be simple (store token + expiry; re-fetch when expired or absent) and SHALL be noted as a POC-level optimization.

## 4. Functional Requirements

- **FR-SR-1** The SmartResume Adapter SHALL expose a router-facing internal contract for the `deliver_to_smartresume` action.
- **FR-SR-2** The SmartResume Adapter SHALL be implemented in Python; SmartResume provides no SDK, so no Node/TypeScript component is required.
- **FR-SR-3** The SmartResume Adapter SHALL validate its required router-facing payload fields before attempting delivery.
- **FR-SR-4** The SmartResume Adapter SHALL obtain a SmartResume OAuth2 access token via `POST /api/v1/token` using HTTP Basic auth with `ClientID` and `AccessKey` before calling the delivery endpoint.
- **FR-SR-5** The SmartResume Adapter SHALL deliver to `POST /api/v1/credentials` using `Authorization: Bearer <access_token>` with a JSON body conforming to the mapping in §3.
- **FR-SR-6** The SmartResume Adapter SHALL omit the `proof` field from the request body when the incoming payload does not include a proof, producing an unverified achievement record acceptable to SmartResume.
- **FR-SR-7** The SmartResume Adapter SHALL pass a `proof` field through verbatim when the incoming payload includes one.
- **FR-SR-8** The SmartResume Adapter SHALL enforce the 40-character limit on `alignment[].targetName` by truncating and logging a warning when the limit is exceeded.
- **FR-SR-9** The SmartResume Adapter SHALL preserve the `redirect_url` returned by SmartResume on success as the normalized `external_reference_id` in its response.
- **FR-SR-10** The SmartResume Adapter SHALL return errors in a structured form that preserves the HTTP status code and any SmartResume error body, allowing the Delivery Router and Orchestrator to distinguish failure from success.
- **FR-SR-11** The SmartResume Adapter SHALL keep `ClientID` and `AccessKey` out of source control and other committed artifacts, resolving them from environment configuration at runtime.
- **FR-SR-12** The SmartResume Adapter SHALL attach or preserve workflow, execution, step, and correlation identifiers in its logs and result records.
- **FR-SR-13** The SmartResume Adapter SHALL resolve its target base URL entirely from configuration (`SMARTRESUME_ADAPTER_API_URL`) with no hard-coded default. The expected value is the Mock SmartResume URL in all current environments (local: `http://localhost:8930`; AWS: the deployed mock's URL). Accessing a real SmartResume environment requires a vendor partnership that is out of scope for this POC.
- **FR-SR-14** The SmartResume Adapter SHALL NOT own delivery target selection, business-policy enforcement, workflow planning, or substantive field mapping.
- **FR-SR-15** The SmartResume Adapter SHALL NOT own LearnCard credential issuance or LearnCard wallet delivery.
- **FR-SR-16** The SmartResume Adapter SHALL NOT attempt CLR 2.0, Verifiable Presentation, or VCALM exchange delivery; those endpoints are out of scope for the POC.

## 5. Out of Scope

The SmartResume Adapter does not own:

- LearnCard credential issuance or wallet delivery,
- transformation mapping generation,
- synthesized field generation,
- policy validation,
- orchestration decisions,
- SmartResume CLR 2.0 (`/clr`), Verifiable Presentation (`/verifiablepresentation`), or VCALM exchange (`/exchanges/{token}`) endpoints, or
- any SmartResume account management, learner signup, or resume editing operations.
