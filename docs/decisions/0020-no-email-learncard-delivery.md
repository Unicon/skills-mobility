# ADR-0020: No-Email LearnCard Delivery for the Demo (Fixed Recipient Wallet + Read-Back)

- Status: Accepted
- Date: 2026-06-30
- Related: [ADR-0016](./0016-delivery-routing-topology.md) · [ADR-0014](./0014-poc-storage-strategy.md) · [ADR-0002](./0002-frontend-architecture.md) · Umbrella [#38](https://github.com/Unicon/skills-mobility/issues/38) · Spikes [#39](https://github.com/Unicon/skills-mobility/issues/39), [#41](https://github.com/Unicon/skills-mobility/issues/41)

## Context

The end-to-end demo must show a credential **actually delivered into a LearnCard wallet**, surfaced as delivered in the Admin UI.

Two spikes against the live LearnCard network established hard constraints:

- **#39:** identities are self-generated from a seed and everything is self-serve (no accounts/no email needed to operate); delivery by `profileId` works via `POST /credential/send/{profileId}`.
- **#41:** LearnCard **Search does not match email**, a service **cannot create a learner's profile** (regular profiles are self-sovereign; managed profiles need Profile-Manager provisioning), and `sendCredential`/`/credential/send/{profileId}` requires the recipient to **already have an account**.

The only way to deliver to a learner who has *no* LearnCard account is LearnCard's **email/Boost-Inbox claim flow** (recipient = email → claim link). That path has two problems for this demo:

1. **Presenter friction.** The demo may be run by different people who do not want to bring up a personal inbox to complete a claim mid-demo.
2. **Added complexity.** It is a different endpoint and a multi-step claim flow, i.e. the one unsolved gap flagged in #41.

## Decision

**The demo avoids email entirely.** Delivery targets a **fixed, pre-provisioned LearnCard recipient wallet** that the team controls, and the Admin UI proves delivery via a **live read-back** of that wallet.

- **Fixed demo recipient wallet** (`smi-demo-learner`): seed-derived, provisioned once via a TS/SDK setup step, reusable by any presenter with zero per-presenter setup. The seed is **derived at runtime from a committed, non-secret demo label** (not a committed raw key); the minted bearer tokens are **gitignored** and regenerable from the seed.
- **Deliver by `profileId`** to that wallet (Wallet Adapter, #43) — no email, no external login.
- **Resolve** the demo learner → the known `profileId` via a seeded stored mapping / handle search (Profile Resolver, #41). The email resolution path is never exercised.
- **Show delivery** via a **read-back**: read the demo wallet's received credentials (a recipient-scoped `credentials:read` token, minted alongside the wallet) and render the delivered badge. Surfaced to the Admin UI through the **Orchestration Service read-API** (the Admin UI is owned separately; the Orchestrator owns the read surface it calls, per ADR-0016's "Orchestration Service still owns the correlated execution view").

The **email / Boost-Inbox delivery path is explicitly out of scope** for the POC.

## Options Considered

| Option | Description | Main concern |
| --- | --- | --- |
| Fixed pre-provisioned recipient wallet + `profileId` delivery + read-back (chosen) | Deliver to a wallet we control; prove delivery by reading it back in-app | Requires a one-time provisioning step and a shared demo identity |
| Email / Boost-Inbox claim flow | Send to a learner's email; they claim into their own wallet | Presenter must open an inbox mid-demo; extra endpoint + multi-step claim; blocks a repeatable no-friction demo |
| Embed the LearnCard wallet app view | Point the demo at learncard.app for the recipient | Requires recipient login (seed/passphrase) — same friction as email |

## Consequences

### Positive

- **Repeatable, presenter-agnostic demo** — no personal inbox, no external login, no per-presenter accounts.
- **Removes the one unsolved gap** (no-account delivery) from #41; #43/#41 stand as built.
- Real in-wallet proof (a live read-back), not just an asserted "accepted".

### Negative

- A **shared demo identity**: whoever has the derived seed controls that wallet. Accepted because it holds only demo badges on the public demo network (mirrors LearnCard's own `'1234'` demo-seed convention). Bearer tokens stay gitignored/regenerable.
- Adds a **provisioning step** ([#52](https://github.com/Unicon/skills-mobility/issues/52)) and a **read-back capability** ([#53](https://github.com/Unicon/skills-mobility/issues/53)).
- The demo does **not** exercise real learner onboarding — an accepted POC limitation.

## Revisit Triggers

- The POC needs to demonstrate delivery to a **real, previously-unknown learner** (then the email/Inbox claim flow or Profile-Manager-managed profiles must be revisited).
- LearnCard adds service-side profile creation or email-indexed search that makes resolution of arbitrary learners viable.
- The demo must run fully offline / without the public LearnCard network.
