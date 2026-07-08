// Issuer configuration resolved from the environment (design §4 step 3, §5).
// SECURE_SEED / PROFILE_ID / PROFILE_NAME are the *issuer* institution's
// LearnCard identity — not the recipient's app profile. Secrets come from a
// gitignored .env locally; Secrets Manager / SSM in AWS.

export interface IssuerConfig {
  port: number;
  secureSeed: string | null;
  profileId: string | null;
  profileName: string | null;
}

export function loadConfig(): IssuerConfig {
  return {
    // 8910 — outside Consul's reserved range (8300-8302, 8500, 8600); 8500 collided
    // with Consul's HTTP API port.
    port: Number(process.env.PORT ?? 8910),
    secureSeed: process.env.SECURE_SEED ?? null,
    profileId: process.env.PROFILE_ID ?? null,
    profileName: process.env.PROFILE_NAME ?? null,
  };
}

// Whether the issuer is fully configured to talk to LearnCard. Until #39
// supplies dev credentials this is false and issuance is not yet wired.
export function isConfigured(cfg: IssuerConfig): boolean {
  return Boolean(cfg.secureSeed && cfg.profileId);
}
