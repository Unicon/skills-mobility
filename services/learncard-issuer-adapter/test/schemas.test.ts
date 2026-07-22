import { describe, expect, it } from "vitest";
import { IssueRequest } from "../src/schemas";

const valid = {
  contract_version: "v1",
  workflow_id: "wf_1",
  execution_id: "exec_1",
  step_id: "step_issuer",
  correlation_id: "corr_1",
  delivery_config_ref: "learncard-dev",
  payload: { unsigned_vc: { type: ["VerifiableCredential"] } },
};

describe("IssueRequest", () => {
  it("accepts a well-formed request", () => {
    const parsed = IssueRequest.safeParse(valid);
    expect(parsed.success).toBe(true);
  });

  it("rejects a request missing the unsigned_vc payload", () => {
    const { payload, ...rest } = valid;
    void payload;
    expect(IssueRequest.safeParse(rest).success).toBe(false);
  });

  it("rejects a wrong contract_version", () => {
    expect(IssueRequest.safeParse({ ...valid, contract_version: "v2" }).success).toBe(false);
  });
});
