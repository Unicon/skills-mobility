import request from "supertest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IssuerConfig } from "../src/config";

// Mock the SDK so the route exercises the real wiring (parse -> issue -> toSuccess/
// toError) without a live LearnCard. issueCredential is reconfigurable per test.
const issueCredentialMock = vi.fn();

vi.mock("@learncard/init", () => ({
  initLearnCard: vi.fn(async () => ({
    id: { did: () => "did:web:network.learncard.com:users:smi-demo-organization" },
    invoke: {
      issueCredential: issueCredentialMock,
      getProfile: vi.fn(async () => ({ profileId: "smi-demo-organization" })),
      createServiceProfile: vi.fn(async () => ({})),
    },
  })),
}));

const cfg: IssuerConfig = {
  port: 8910,
  secureSeed: "deadbeef",
  profileId: "smi-demo-organization",
  profileName: "SMI Demo Organization",
};

const validBody = {
  contract_version: "v1",
  workflow_id: "wf_1",
  execution_id: "exec_1",
  step_id: "step_issue",
  correlation_id: "corr_1",
  delivery_config_ref: "learncard-dev",
  payload: {
    unsigned_vc: {
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      type: ["VerifiableCredential"],
      credentialSubject: { id: "did:web:network.learncard.com:users:smi-demo-learner" },
    },
  },
};

async function app() {
  vi.resetModules(); // fresh memoized issuer per test
  const { createApp } = await import("../src/api");
  return createApp(cfg);
}

beforeEach(() => {
  vi.clearAllMocks();
  issueCredentialMock.mockImplementation(async (vc: Record<string, unknown>) => ({
    ...vc,
    id: "urn:cred:abc-123",
    proof: { type: "DataIntegrityProof", cryptosuite: "eddsa-rdfc-2022" },
  }));
});

describe("POST /internal/issue-learncard-badge", () => {
  it("returns 422 on an invalid request body", async () => {
    const res = await request(await app())
      .post("/internal/issue-learncard-badge")
      .send({ not: "a valid IssueRequest" });
    expect(res.status).toBe(422);
    expect(res.body.status).toBe("failed");
    expect(res.body.error.code).toBe("invalid_request");
  });

  it("issues and returns the success envelope", async () => {
    const res = await request(await app())
      .post("/internal/issue-learncard-badge")
      .send(validBody);
    expect(res.status).toBe(200);
    expect(res.body.status).toBe("succeeded");
    expect(res.body.external_reference_id).toBe("urn:cred:abc-123");
    expect(res.body.result.issued_credential.proof.type).toBe("DataIntegrityProof");
  });

  it("normalizes a signer failure into status:failed with HTTP 200", async () => {
    issueCredentialMock.mockRejectedValue(new Error("signer boom"));
    const res = await request(await app())
      .post("/internal/issue-learncard-badge")
      .send(validBody);
    expect(res.status).toBe(200); // normalized envelope, never leaks an HTTP error
    expect(res.body.status).toBe("failed");
    expect(res.body.result).toBeNull();
    expect(res.body.error.message).toMatch(/signer boom/);
  });
});

describe("GET /healthz", () => {
  it("reports ok and configured", async () => {
    const res = await request(await app()).get("/healthz");
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: "ok", configured: true });
  });
});
