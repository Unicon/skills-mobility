# learncard-issuer-adapter — LearnCard Issuer Adapter (Node/TS)

The thin Node/TypeScript boundary around the **LearnCard SDK** that signs an
already-shaped unsigned OBv3 and returns the issued credential (issue #42; design:
[`docs/3_design/learncard-issuer-adapter.md`](../../docs/3_design/learncard-issuer-adapter.md)).
It is the one TypeScript **service** in the stack (the LearnCard SDK forces a
Node/TS runtime — AGENTS.md / ADR-0003). It does **not** resolve recipient
profiles (that's the Profile Resolver) or route (that's the Delivery Router).

> **Status: wired to the LearnCard SDK.** `issueCredential` initializes the issuer
> wallet from `SECURE_SEED` (memoized), ensures the issuer **service profile**
> exists (`getProfile` → `createServiceProfile` if absent — design §4 step 5), and
> signs the unsigned OBv3 via `invoke.issueCredential` — a real `DataIntegrityProof`
> is attached. Until `SECURE_SEED` + `PROFILE_ID` are set, `/healthz` reports
> `configured: false` and issuance returns a normalized `failed` result.

## Layout

```
src/
  server.ts    entry: builds the app and listens
  api.ts       POST /internal/issue-learncard-badge + /healthz
  schemas.ts   zod request schema + response type (router-facing contract)
  learncard.ts LearnCard SDK init (memoized) + profile assurance + issueCredential
  resultmap.ts normalize SDK results/errors → response shape
  config.ts    env config (PORT, LOG_LEVEL, SECURE_SEED, PROFILE_ID, PROFILE_NAME)
  logger.ts    minimal LOG_LEVEL-gated logger
test/          vitest tests: schema validation, SDK wrapper (mocked), HTTP route (supertest)
```

## Setup: issuer seed + profile

The adapter signs as the issuing institution — the demo **organization** profile.
A LearnCard network profile can only be signed for with the seed its keys were
derived from, so the seed isn't arbitrary: a random seed can't issue as an
existing identity (it hits `Profile already exists!` then `Key mismatch`).

```bash
cd services/learncard-issuer-adapter
cp .env.example .env
```

**Coordinated demo (default).** The identity is the `organization` profile that
`tools/learncard-demo` provisions (`smi-demo-organization`, ADR-0020, PR #54). The
adapter **derives the seed from the public label** — the same scheme as that tool
(`deriveSeed('organization')`) — so no secret is copied by hand. `.env.example`
already ships these values; edit `.env` **in place** (don't append — that
duplicates keys) if you need to change them:

```
SEED_LABEL=organization
PROFILE_ID=smi-demo-organization
PROFILE_NAME=SMI Demo Organization
```

**Standalone throwaway identity.** To stand up your *own* fresh identity instead,
set a raw `SECURE_SEED` (e.g. `openssl rand -hex 32`) **and** a `PROFILE_ID` that
is not already registered — the adapter creates that new service profile on first
issuance. `SECURE_SEED`, when set, overrides `SEED_LABEL`. Until a seed + profile
resolve, `/healthz` reports `configured: false`.

### Sample request payload

`payload.unsigned_vc` is a full unsigned OBv3; the recipient's resolved LearnCard
DID goes in **`credentialSubject.id`** (the Profile Resolver put it there upstream):

```json
{
  "contract_version": "v1",
  "workflow_id": "wf_1", "execution_id": "exec_1", "step_id": "step_issue",
  "correlation_id": "corr_1", "delivery_config_ref": "learncard-dev",
  "payload": {
    "unsigned_vc": {
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      "type": ["VerifiableCredential", "OpenBadgeCredential"],
      "issuer": "did:web:network.learncard.com:users:smi-demo-organization",
      "credentialSubject": {
        "id": "did:web:network.learncard.com:users:smi-demo-learner",
        "type": ["AchievementSubject"],
        "achievement": { "id": "urn:uuid:...", "name": "Intro to Accounting" }
      }
    }
  }
}
```

## Contract

`POST /internal/issue-learncard-badge` (called by the Delivery Router) — request as
above → `{ "status": "succeeded|failed", "external_reference_id": "...",
"result": { "issued_credential": { } }, "error": null }`.

## Run / test

```bash
cd services/learncard-issuer-adapter
npm install
npm run dev                 # tsx watch — serves on :8910 (no Swagger; see the contract above)
npm run build               # tsc → dist/
npm run typecheck           # tsc --noEmit
npm test                    # vitest (schema + SDK-wrapper + route tests)
```

`curl localhost:8910/healthz` → `{"status":"ok","configured":true}` once `SECURE_SEED` + `PROFILE_ID` are set. (Port 8910 is outside Consul's reserved range — 8300–8302, 8500, 8600.)

## Downstream

The signed credential returned here flows back through the Delivery Router (#44)
to the Wallet Adapter (#43), which delivers it to the recipient's LearnCard
wallet by `profileId`. Issuance signs only; it never delivers.
