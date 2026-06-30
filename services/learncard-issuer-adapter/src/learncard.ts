import { type IssuerConfig, isConfigured } from "./config";

export class IssuerNotConfiguredError extends Error {
  readonly code = "issuer_not_configured";
}

export interface IssuanceResult {
  externalReferenceId: string;
  issuedCredential: Record<string, unknown>;
}

/**
 * Wraps the LearnCard SDK issuance call (design §3 `learncard/`, §4 steps 4–7).
 *
 * TODO(#42): once #39 supplies SECURE_SEED + the issuer service profile, implement:
 *   const issuer = await initLearnCard({ seed, network: true, allowRemoteContexts: true });
 *   // ensure the issuer service profile exists (lookup/create);
 *   const signed = await issuer.invoke.issueCredential(unsignedVc);
 * and map `signed` into IssuanceResult. The LearnCard SDK dependency
 * (@learncard/init) is added in that step — kept out of this toolchain slice so
 * the build is self-contained until credentials exist.
 */
export async function issueCredential(
  cfg: IssuerConfig,
  unsignedVc: Record<string, unknown>,
): Promise<IssuanceResult> {
  void unsignedVc; // consumed once the SDK call is wired
  if (!isConfigured(cfg)) {
    throw new IssuerNotConfiguredError(
      "LearnCard issuer not configured: set SECURE_SEED + PROFILE_ID (blocked on #39).",
    );
  }
  throw new IssuerNotConfiguredError("LearnCard SDK issuance not yet wired (#42 steps 2–4).");
}
