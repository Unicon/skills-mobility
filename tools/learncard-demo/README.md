# learncard-demo (provisioning)

One-time setup for the **no-email** LearnCard demo ([ADR-0020](../../docs/decisions/0020-no-email-learncard-delivery.md), [#52](https://github.com/Unicon/skills-mobility/issues/52)). Stands up two fixed demo identities on the LearnCard network — a **demo learner** (recipient) and a **demo organization** (the issuing institution) — and mints the bearer tokens the demo needs, no personal inbox, no per-presenter accounts.

This provisions two independent personas. Understanding them separately matters for what each is used for and by whom.

## Demo Learner (recipient)

**Inputs** (`.env`)
- `RECIPIENT_LABEL` — public, committed label used to derive the seed (default `learner`)
- `RECIPIENT_PROFILE_ID` — the network profile id to create/reuse (default `smi-demo-learner`)

**Outputs** (written to the generated `.env`)
- `LEARNCARD_RECIPIENT_API_TOKEN` — `credentials:read` scoped bearer
- `DEMO_RECIPIENT_PROFILE_ID`, `DEMO_RECIPIENT_DID`

**Used by**
- The delivered-credential read-back for the Admin UI (#53)
- Seeds the Profile Resolver's stored mapping (`profile_id` → these values)

## Demo Organization (issuing institution)

**Inputs** (`.env`)
- `ORGANIZATION_LABEL` — public, committed label used to derive the seed (default `organization`)
- `ORGANIZATION_PROFILE_ID` — the network profile id to create/reuse (default `smi-demo-organization`)

**Outputs** (written to the generated `.env`)
- `LEARNCARD_API_TOKEN` — `credentials:write` scoped bearer (the "sender" token)
- `DEMO_ORGANIZATION_PROFILE_ID`, `DEMO_ORGANIZATION_DID`

**Used by**
- Wallet Adapter (#43) and Profile Resolver (#41) — copy `LEARNCARD_API_TOKEN` into each service's `.env`

**Not covered here:** the Issuer Adapter's own `SECURE_SEED`/`PROFILE_NAME` (needed for in-process credential signing) — this tool doesn't derive or expose those today (tracked in #66).

## Why this is safe

The *seeds* are derived from public, committed labels (no raw key committed) — only the *tokens*, the real secrets, are written out, and they go into a **gitignored `.env`**, regenerable any time by re-running provisioning. Both wallets hold only demo badges on the public demo network (mirrors LearnCard's own `'1234'` demo-seed convention).

## Run

```bash
cd tools/learncard-demo
npm install
cp .env.example .env        # override RECIPIENT_*/ORGANIZATION_* here for a different demo identity
npm run provision           # needs network access to network.learncard.com
```

Then copy the generated tokens into the service `.env` files — see "Used by" above.

## Test

```bash
npm test      # node --test — covers the deterministic seed derivation
```

The live provisioning (network calls) is verified by running it, not unit-tested.
