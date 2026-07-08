import { initLearnCard } from "@learncard/init";
import { type IssuerConfig, isConfigured } from "./config";

export class IssuerNotConfiguredError extends Error {
  readonly code = "issuer_not_configured";
}

export interface IssuanceResult {
  externalReferenceId: string;
  issuedCredential: Record<string, unknown>;
}

// Minimal structural view of the LearnCard wallet. The SDK's plugin-composed
// type isn't practical to name here (initLearnCard is heavily overloaded), so we
// type only the members this adapter calls and cast the instance to it.
interface IssuerWallet {
  id: { did: () => string };
  invoke: {
    issueCredential: (vc: Record<string, unknown>) => Promise<Record<string, unknown>>;
    // #48 review / design §4 step 5: the issuer service-profile assurance methods
    // (@learncard/network-plugin — LCNProfile maps profileId/displayName directly).
    getProfile: (profileId?: string) => Promise<unknown>;
    createServiceProfile: (input: {
      profileId: string;
      displayName: string;
      isServiceProfile: boolean;
    }) => Promise<unknown>;
  };
}

/**
 * Ensure the issuer's LearnCard service profile exists before issuance
 * (design §4 step 5, FR-LCI-6): look it up, create it from PROFILE_ID/PROFILE_NAME
 * if absent. Idempotent — a create that reports "already exists" is benign on
 * re-run; any other failure surfaces rather than being swallowed.
 *
 * NOTE: wired to the SDK methods named in the #48 review, but the create path
 * can't be exercised against a live network here — verify once with real issuer
 * credentials.
 */
async function ensureIssuerProfile(wallet: IssuerWallet, cfg: IssuerConfig): Promise<void> {
  const existing = await wallet.invoke.getProfile();
  if (existing) return;
  try {
    await wallet.invoke.createServiceProfile({
      profileId: cfg.profileId as string,
      displayName: cfg.profileName ?? (cfg.profileId as string),
      isServiceProfile: true,
    });
  } catch (err) {
    const message = String((err as { message?: unknown })?.message ?? err);
    if (!/exist|already|taken|conflict/i.test(message)) throw err;
  }
}

// The initialized issuer wallet is expensive to create (network + key setup), so
// it is memoized across requests. A failed init clears the cache so the next
// request retries rather than sticking to a rejected promise. Profile assurance
// runs once as part of init (before the wallet is cached).
let issuerPromise: Promise<IssuerWallet> | null = null;

function getIssuer(cfg: IssuerConfig): Promise<IssuerWallet> {
  if (!issuerPromise) {
    // allowRemoteContexts lets the signer resolve the OBv3 JSON-LD @context refs.
    issuerPromise = initLearnCard({
      seed: cfg.secureSeed as string,
      network: true,
      allowRemoteContexts: true,
    })
      .then(async (lc) => {
        const wallet = lc as unknown as IssuerWallet;
        await ensureIssuerProfile(wallet, cfg);
        return wallet;
      })
      .catch((err: unknown) => {
        issuerPromise = null;
        throw err;
      });
  }
  return issuerPromise;
}

/**
 * Signs the unsigned OBv3 with the issuer's LearnCard key (design §4 steps 4–7).
 * The recipient DID is already in `credentialSubject.id` (resolved upstream by the
 * Profile Resolver); this adapter only issues (signs) — delivery is the Wallet
 * Adapter's job. The issuer's own service profile is ensured at init (§4 step 5).
 */
export async function issueCredential(
  cfg: IssuerConfig,
  unsignedVc: Record<string, unknown>,
): Promise<IssuanceResult> {
  if (!isConfigured(cfg)) {
    throw new IssuerNotConfiguredError(
      "LearnCard issuer not configured: set SECURE_SEED + PROFILE_ID.",
    );
  }
  const issuer = await getIssuer(cfg);
  const signed = await issuer.invoke.issueCredential(unsignedVc);
  // Issuance produces a signed VC (no external delivery yet); reference it by its
  // credential id when present, else the issuer DID.
  const externalReferenceId = typeof signed.id === "string" ? signed.id : issuer.id.did();
  return { externalReferenceId, issuedCredential: signed };
}
