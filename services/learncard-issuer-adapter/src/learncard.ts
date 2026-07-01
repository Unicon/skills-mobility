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
  invoke: { issueCredential: (vc: Record<string, unknown>) => Promise<Record<string, unknown>> };
}

// The initialized issuer wallet is expensive to create (network + key setup), so
// it is memoized across requests. A failed init clears the cache so the next
// request retries rather than sticking to a rejected promise.
let issuerPromise: Promise<IssuerWallet> | null = null;

function getIssuer(cfg: IssuerConfig): Promise<IssuerWallet> {
  if (!issuerPromise) {
    // allowRemoteContexts lets the signer resolve the OBv3 JSON-LD @context refs.
    issuerPromise = initLearnCard({
      seed: cfg.secureSeed as string,
      network: true,
      allowRemoteContexts: true,
    })
      .then((lc) => lc as unknown as IssuerWallet)
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
 * Adapter's job. The issuer's LearnCard profile is provisioned separately (#52).
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
