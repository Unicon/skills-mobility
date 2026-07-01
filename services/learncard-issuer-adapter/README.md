# learncard-issuer-adapter — LearnCard Issuer Adapter (Node/TS)

The thin Node/TypeScript boundary around the **LearnCard SDK** that signs an
already-shaped unsigned OBv3 and returns the issued credential (issue #42; design:
[`docs/3_design/learncard-issuer-adapter.md`](../../docs/3_design/learncard-issuer-adapter.md)).
It is the one TypeScript **service** in the stack (the LearnCard SDK forces a
Node/TS runtime — AGENTS.md / ADR-0003). It does **not** resolve recipient
profiles (that's the Profile Resolver) or route (that's the Delivery Router).

> **Status: wired to the LearnCard SDK.** `issueCredential` initializes the issuer
> wallet from `SECURE_SEED` (memoized) and signs the unsigned OBv3 via
> `invoke.issueCredential` — verified live (a real `DataIntegrityProof` is attached).
> Until `SECURE_SEED` + `PROFILE_ID` are set, `/healthz` reports `configured: false`
> and issuance returns a normalized `failed` result. Seed/profile come from the demo
> provisioning step (`tools/learncard-demo`, ADR-0020).

## Layout

```
src/
  server.ts    entry: builds the app and listens
  api.ts       POST /internal/issue-learncard-badge + /healthz
  schemas.ts   zod request schema + response type (router-facing contract)
  learncard.ts LearnCard SDK init (memoized) + issueCredential signing wrapper
  resultmap.ts normalize SDK results/errors → response shape
  config.ts    env config (PORT, LOG_LEVEL, SECURE_SEED, PROFILE_ID, PROFILE_NAME)
  logger.ts    minimal LOG_LEVEL-gated logger
test/          vitest unit tests (schema validation, result normalization)
```

## Contract

`POST /internal/issue-learncard-badge` (called by the Delivery Router):

```json
{ "contract_version": "v1", "workflow_id": "...", "execution_id": "...",
  "step_id": "...", "correlation_id": "...", "delivery_config_ref": "learncard-dev",
  "payload": { "unsigned_vc": { } } }
```

→ `{ "status": "succeeded|failed", "external_reference_id": "...",
     "result": { "issued_credential": { } }, "error": null }`

## Run / test

```bash
cd services/learncard-issuer-adapter
npm install
cp .env.example .env        # SECURE_SEED + PROFILE_ID from tools/learncard-demo
npm run dev                 # tsx watch — serves on :8500 (Swagger N/A; see contract above)
npm run build               # tsc → dist/
npm run typecheck           # tsc --noEmit
npm test                    # vitest
```

`curl localhost:8500/healthz` → `{"status":"ok","configured":true}` once `SECURE_SEED` + `PROFILE_ID` are set.

## Downstream

The signed credential returned here flows back through the Delivery Router (#44)
to the Wallet Adapter (#43), which delivers it to the recipient's LearnCard
wallet by `profileId`. Issuance signs only; it never delivers.
