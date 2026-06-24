# LearnCard Issuer Adapter Design

Status: Draft
Date: 2026-06-22
Related: [Requirements](../2_requirements/learncard-issuer-adapter.md) · [Delivery Router Service Design](./delivery-router-service.md) · [LearnCard Wallet Adapter Design](./learncard-wallet-adapter.md) · [LearnCard Profile Resolver Design](./learncard-profile-resolver.md) · [ADR-0003](../decisions/0003-programming-language.md) · [ADR-0016](../decisions/0016-delivery-routing-topology.md) · [LearnCard tutorial: Create a Credential](https://docs.learncard.com/tutorials/create-a-credential) · [LearnCard guide: Send Credentials](https://docs.learncard.com/how-to-guides/send-credentials)

## 1. Overview

The LearnCard Issuer Adapter is a dedicated Node/TypeScript service boundary around the LearnCard SDK.

| Part | Expected path | Tech | Role |
|---|---|---|---|
| Service | `services/learncard-issuer-adapter/` | TypeScript + LearnCard SDK | Issue and sign a credential from an already-shaped issuer payload |

The adapter is intentionally thin. The transformation pipeline shapes the payload upstream; the adapter performs only final SDK binding and returns a normalized result.

For **Phase 1**, read that as "the Orchestrator shapes the payload upstream." For the **full POC**, that shaping responsibility is expected to move into the transformation pipeline.

The official LearnCard documentation is specific enough to guide this design:

- initialize the issuer instance with `initLearnCard`,
- pass secure seed material plus `network: true`,
- allow remote contexts for remote VC contexts when needed,
- ensure a service profile exists before sending or issuing on the network,
- issue the VC with `learnCardIssuer.invoke.issueCredential(unsignedVc)`.

The same docs also show higher-level `sendCredential` and `send` flows that can deliver the credential after issuance. This design intentionally stops at issuance so the POC can keep issuance and wallet delivery as separate internal steps.

To avoid ambiguity, the adapter design should treat the following as separate identities:

- **Issuer seed**: secret material used to derive the issuer DID and signing keys.
- **Issuer service profile**: the LearnCard-network profile bound to that issuer identity. In this architecture, it should represent the issuing institution or issuing service.
- **Recipient Profile ID**: the case-sensitive LearnCard app profile of the learner receiving the credential.

**Recipient profile resolution — upstream dependency.** The `unsigned_vc.credentialSubject.id` embedded in the request payload should contain the recipient's LearnCard-resolved DID, derived from their LearnCard profile. That resolution is owned by the **LearnCard Profile Resolver** ([design](./learncard-profile-resolver.md)), a standalone Lambda that the Orchestrator invokes as a named plan step before this adapter is called. The Orchestrator passes the resolved DID in the pre-shaped unsigned VC. This adapter does not perform or re-perform recipient profile resolution.

## 2. Invocation Model

Recommended endpoint:

```text
POST /internal/issue-learncard-badge
```

Recommended request shape:

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_123",
  "execution_id": "exec_123",
  "step_id": "step_issuer",
  "correlation_id": "corr_123",
  "delivery_config_ref": "learncard-dev",
  "payload": {
    "unsigned_vc": {}
  }
}
```

Recommended response shape:

```json
{
  "status": "succeeded",
  "external_reference_id": "ext_123",
  "result": {
    "issued_credential": {}
  },
  "error": null
}
```

The router remains responsible for the outer delivery-action envelope. The issuer adapter owns only this adapter-specific contract.

The request payload should therefore map cleanly onto the unsigned VC shape expected by LearnCard's issuance flow, not an arbitrary vendor-specific blob.

The adapter configuration should also map cleanly onto the LearnCard concepts shown in the official tutorial, including secure seed material plus service-profile metadata equivalent to `SECURE_SEED`, `PROFILE_ID`, and `PROFILE_NAME`.

That means `PROFILE_ID` / `PROFILE_NAME` here are issuer-facing configuration values for the issuing institution's LearnCard identity, not the recipient's app profile.

## 3. Modules

- `api/` — internal issuer endpoint
- `schemas/` — request and response models
- `learncard/` — SDK initialization, service-profile assurance, and issuance call wrapper
- `config/` — environment/config resolution for issuer profile and credentials
- `resultmap/` — normalize LearnCard SDK responses and errors

The adapter should not contain policy logic, delivery-target selection, or generic routing behavior.

## 4. Execution Flow

1. Receive the issuer request from the Delivery Router.
2. Validate the required contract fields.
3. Resolve the LearnCard configuration referenced by `delivery_config_ref`, including secure seed and service-profile metadata.
4. Initialize the LearnCard SDK using the documented issuer setup pattern, including network capability and remote-context support as needed.
5. Ensure the issuer service profile exists, using the LearnCard profile lookup/create flow or an equivalent supported mechanism.
6. Apply any minor final parameter or envelope adjustments required by the SDK.
7. Execute the LearnCard issuance/signing call through `invoke.issueCredential(...)` or its supported successor.
8. Normalize the SDK result into the adapter response shape.
9. Return the issued credential artifact to the router.

If Step 6 starts doing substantial field mapping or schema translation, that is a boundary smell and the transformation pipeline should be revisited instead.

If a future LearnCard SDK revision changes these concrete call names or setup details, the adapter should absorb that change without changing the router-facing contract.

## 5. Deployment Shape

The expected deployment shape is a separate Lambda-sized service or equivalent internal service because the LearnCard SDK forces a Node/TypeScript runtime boundary.

The more important design rule is not the exact hosting model. It is that the Orchestrator and router remain isolated from LearnCard SDK types and mechanics.

### Local Development

| Concern | AWS | Local |
|---|---|---|
| Runtime | Lambda | `ts-node` or compiled `node` serving the endpoint locally |
| Secrets | Secrets Manager / SSM Parameter Store | `.env` file (gitignored; `.env.example` committed) |
| LearnCard SDK | Production or staging seed from Secrets Manager | Dev seed loaded from `.env` |
| LearnCard network | Production or staging environment | LearnCard dev environment (no local mock needed) |

No store dependency means no additional local infrastructure is needed beyond the `.env` file.

## 6. Testing

- Unit tests around request validation and result normalization
- Adapter-level tests with the LearnCard SDK mocked
- Contract tests that verify the router-facing request/response shape
- Optional integration tests against a real LearnCard environment only when credentials are intentionally supplied

Routine test runs should not require live LearnCard access.

## 7. Build Order

1. Define the adapter request/response schemas.
2. Implement SDK initialization from secure seed-backed config.
3. Implement issuer service-profile lookup/create behavior.
4. Wrap the LearnCard `issueCredential` call and normalize the returned signed VC.
5. Add normalized result and error mapping.
6. Wire the adapter to the Delivery Router.
