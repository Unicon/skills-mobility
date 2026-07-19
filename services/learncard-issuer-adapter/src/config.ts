// Issuer configuration resolved from the environment (design §4 step 3, §5).
// SECURE_SEED / PROFILE_ID / PROFILE_NAME are the issuing institution's LearnCard
// identity (the demo "organization" profile — an institution that hosts both an
// issuer and a wallet, #54) — not the recipient's app profile. Secrets come from
// a gitignored .env locally; Secrets Manager / SSM in AWS.

import { createHash } from "node:crypto";

export interface IssuerConfig {
  port: number;
  secureSeed: string | null;
  profileId: string | null;
  profileName: string | null;
}

// Deterministically derive a LearnCard seed (64-char hex) from a public,
// non-secret label — the same scheme as tools/learncard-demo (ADR-0020). This
// lets the demo reproduce a fixed identity's keypair (e.g. `organization`, which
// owns `smi-demo-organization`) without committing the raw seed. A registered
// network profile can only be signed for with the seed its keys were derived
// from, so a random seed cannot issue as an existing identity — hence the label.
export function deriveSeed(label: string): string {
  return createHash("sha256").update(`skills-mobility-demo:${label}`).digest("hex");
}

export function loadConfig(): IssuerConfig {
  // SECURE_SEED wins (arbitrary identities); otherwise derive from SEED_LABEL so
  // the documented demo path reproduces the provisioned organization identity.
  const rawSeed = process.env.SECURE_SEED?.trim() || null;
  const seedLabel = process.env.SEED_LABEL?.trim() || null;
  return {
    // 8910 — outside Consul's reserved range (8300-8302, 8500, 8600); 8500 collided
    // with Consul's HTTP API port.
    port: Number(process.env.PORT ?? 8910),
    secureSeed: rawSeed ?? (seedLabel ? deriveSeed(seedLabel) : null),
    profileId: process.env.PROFILE_ID ?? null,
    profileName: process.env.PROFILE_NAME ?? null,
  };
}

// Whether the issuer is fully configured to talk to LearnCard. Until #39
// supplies dev credentials this is false and issuance is not yet wired.
export function isConfigured(cfg: IssuerConfig): boolean {
  return Boolean(cfg.secureSeed && cfg.profileId);
}
