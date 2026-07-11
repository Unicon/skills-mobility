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

The adapter needs a LearnCard wallet **seed** and a **service-profile id**. Two ways:

**Self-serve (stand it up / smoke-test now).** The seed is any 64-char hex; the
adapter creates the service profile on first issuance if it doesn't exist, so no
separate profile step is needed (seed generation + profile creation are self-serve
against the public demo network — #39 finding):

```bash
cd services/learncard-issuer-adapter
cp .env.example .env
```

Then edit `.env` **in place** (don't append — that duplicates the keys already in
`.env.example`) and set a LearnCard wallet seed plus the profile:

```
SECURE_SEED=<64-char hex, e.g. from `openssl rand -hex 32`>
PROFILE_ID=smi-demo-issuer
PROFILE_NAME=SMI Demo Issuer
```

**Coordinated demo.** In the full demo the issuing identity is the *organization*
profile that `tools/learncard-demo` provisions (`smi-demo-organization`, ADR-0020,
PR #54), wired to this adapter through docker-compose (`SECURE_SEED` / `PROFILE_ID`
in the demo environment) rather than copied by hand. That tool provisions the
network profile and mints delivery tokens; it does not emit a reusable seed file,
so use the self-serve path above for standalone smoke-testing.

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
      "issuer": "did:web:network.learncard.com:users:smi-demo-issuer",
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
