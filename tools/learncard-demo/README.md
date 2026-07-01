# learncard-demo (provisioning)

One-time setup for the **no-email** LearnCard demo ([ADR-0020](../../docs/decisions/0020-no-email-learncard-delivery.md), [#52](https://github.com/Unicon/skills-mobility/issues/52)). Stands up the two fixed demo identities on the LearnCard network and mints the bearer tokens the demo needs — no personal inbox, no per-presenter accounts.

## What it does

- Derives the **issuer** and **recipient** (`smi-demo-learner`) wallets deterministically from committed, non-secret demo labels (`deriveSeed`), so the wallets are identical for every presenter.
- Ensures both network **profiles** exist (idempotent — safe to re-run).
- Mints two tokens: a **sender** token (issuer, `credential:write`) for delivery, and a **recipient read** token (`credential:read`) for the Admin UI read-back.
- Writes them to a **gitignored `.env`** (regenerable any time from the seeds).

Why this is safe: the *seed* is derived from a public label (no raw key committed), and the *tokens* — the real secrets — are gitignored. The wallet holds only demo badges on the public demo network (mirrors LearnCard's own `'1234'` demo-seed convention).

## Run

```bash
cd tools/learncard-demo
npm install
npm run provision      # needs network access to network.learncard.com
```

Then copy the generated tokens into the service `.env` files:
- `LEARNCARD_API_TOKEN` → Wallet Adapter (#43) + Profile Resolver (#41)
- `LEARNCARD_RECIPIENT_API_TOKEN` + `DEMO_RECIPIENT_*` → the read-back (#53)
- Seed the resolver mapping: `profile_id` → `DEMO_RECIPIENT_PROFILE_ID` / `DEMO_RECIPIENT_DID`

## Test

```bash
npm test      # node --test — covers the deterministic seed derivation
```

The live provisioning (network calls) is verified by running it, not unit-tested.
