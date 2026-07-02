import { describe, expect, it, vi } from "vitest";
import type { IssuerConfig } from "../src/config";

// Mock the LearnCard SDK: a wallet whose issueCredential just attaches a proof.
vi.mock("@learncard/init", () => ({
  initLearnCard: vi.fn(async () => ({
    id: { did: () => "did:web:network.learncard.com:users:smi-demo-issuer" },
    invoke: {
      issueCredential: vi.fn(async (vc: Record<string, unknown>) => ({
        ...vc,
        proof: { type: "Ed25519Signature2020" },
      })),
    },
  })),
}));

import { IssuerNotConfiguredError, issueCredential } from "../src/learncard";

const configured: IssuerConfig = {
  port: 8500,
  secureSeed: "deadbeef",
  profileId: "smi-demo-issuer",
  profileName: null,
};
const unconfigured: IssuerConfig = { port: 8500, secureSeed: null, profileId: null, profileName: null };

describe("issueCredential", () => {
  it("throws IssuerNotConfiguredError when seed/profile are missing", async () => {
    await expect(issueCredential(unconfigured, {})).rejects.toBeInstanceOf(IssuerNotConfiguredError);
  });

  it("signs the unsigned VC and returns the issued credential", async () => {
    const unsigned = {
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      type: ["VerifiableCredential"],
      credentialSubject: { id: "did:web:network.learncard.com:users:smi-demo-learner" },
    };
    const result = await issueCredential(configured, unsigned);

    expect(result.issuedCredential.proof).toBeDefined();
    expect(result.issuedCredential.credentialSubject).toEqual(unsigned.credentialSubject);
    // No `id` on the signed VC -> reference falls back to the issuer DID.
    expect(result.externalReferenceId).toBe("did:web:network.learncard.com:users:smi-demo-issuer");
  });
});
