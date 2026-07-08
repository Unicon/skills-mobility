import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IssuerConfig } from "../src/config";

// Mock the LearnCard SDK. The invoke methods are reconfigurable per test so we can
// exercise both the profile-exists and profile-absent paths and a signer failure.
const issueCredentialMock = vi.fn();
const getProfileMock = vi.fn();
const createServiceProfileMock = vi.fn();

vi.mock("@learncard/init", () => ({
  initLearnCard: vi.fn(async () => ({
    id: { did: () => "did:web:network.learncard.com:users:smi-demo-issuer" },
    invoke: {
      issueCredential: issueCredentialMock,
      getProfile: getProfileMock,
      createServiceProfile: createServiceProfileMock,
    },
  })),
}));

const configured: IssuerConfig = {
  port: 8910,
  secureSeed: "deadbeef",
  profileId: "smi-demo-issuer",
  profileName: "SMI Demo Issuer",
};
const unconfigured: IssuerConfig = {
  port: 8910,
  secureSeed: null,
  profileId: null,
  profileName: null,
};

// Fresh module per test: the issuer wallet (and its one-time profile assurance) is
// memoized at module scope, so a reset lets each test drive it with its own mocks.
async function load() {
  vi.resetModules();
  return import("../src/learncard");
}

beforeEach(() => {
  vi.clearAllMocks();
  issueCredentialMock.mockImplementation(async (vc: Record<string, unknown>) => ({
    ...vc,
    // Real LearnCard output is a DataIntegrityProof (matches the README status line).
    proof: { type: "DataIntegrityProof", cryptosuite: "eddsa-rdfc-2022" },
  }));
  getProfileMock.mockResolvedValue({ profileId: "smi-demo-issuer" }); // exists by default
  createServiceProfileMock.mockResolvedValue({});
});

describe("issueCredential", () => {
  it("throws IssuerNotConfiguredError when seed/profile are missing", async () => {
    const { issueCredential, IssuerNotConfiguredError } = await load();
    await expect(issueCredential(unconfigured, {})).rejects.toBeInstanceOf(IssuerNotConfiguredError);
  });

  it("signs the unsigned VC and returns the issued credential", async () => {
    const { issueCredential } = await load();
    const unsigned = {
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      type: ["VerifiableCredential"],
      credentialSubject: { id: "did:web:network.learncard.com:users:smi-demo-learner" },
    };
    const result = await issueCredential(configured, unsigned);

    expect((result.issuedCredential.proof as { type: string }).type).toBe("DataIntegrityProof");
    expect(result.issuedCredential.credentialSubject).toEqual(unsigned.credentialSubject);
    // No `id` on the signed VC -> reference falls back to the issuer DID.
    expect(result.externalReferenceId).toBe("did:web:network.learncard.com:users:smi-demo-issuer");
  });

  it("creates the issuer service profile when it doesn't exist yet (FR-LCI-6)", async () => {
    getProfileMock.mockResolvedValue(null); // no profile on the network yet
    const { issueCredential } = await load();
    await issueCredential(configured, {});

    expect(createServiceProfileMock).toHaveBeenCalledTimes(1);
    expect(createServiceProfileMock).toHaveBeenCalledWith({
      profileId: "smi-demo-issuer",
      displayName: "SMI Demo Issuer",
      isServiceProfile: true,
    });
  });

  it("does not re-create the profile when it already exists", async () => {
    getProfileMock.mockResolvedValue({ profileId: "smi-demo-issuer" });
    const { issueCredential } = await load();
    await issueCredential(configured, {});

    expect(createServiceProfileMock).not.toHaveBeenCalled();
  });

  it("propagates a LearnCard signer failure (normalization happens at the boundary)", async () => {
    issueCredentialMock.mockRejectedValue(new Error("LearnCard signer rejected the credential"));
    const { issueCredential } = await load();
    await expect(issueCredential(configured, {})).rejects.toThrow(/signer rejected/);
  });

  it("still issues when profile assurance fails (best-effort, non-fatal)", async () => {
    // Reproduces the e2e crash: a live LearnCloud getProfile 500 must NOT crash or
    // fail issuance — the issuer signs with local seed-derived keys regardless.
    getProfileMock.mockRejectedValue(new Error("TRPCClientError: Unable to transform response"));
    const { issueCredential } = await load();
    const result = await issueCredential(configured, { type: ["VerifiableCredential"] });
    expect((result.issuedCredential.proof as { type: string }).type).toBe("DataIntegrityProof");
  });
});
