import { describe, expect, it } from "vitest";
import { IssuerNotConfiguredError } from "../src/learncard";
import { toError, toSuccess } from "../src/resultmap";

describe("resultmap", () => {
  it("normalizes a success into the adapter response shape", () => {
    const out = toSuccess({ externalReferenceId: "ext_1", issuedCredential: { id: "vc_1" } });
    expect(out).toEqual({
      status: "succeeded",
      external_reference_id: "ext_1",
      result: { issued_credential: { id: "vc_1" } },
      error: null,
    });
  });

  it("normalizes an error, carrying a code when present", () => {
    const out = toError(new IssuerNotConfiguredError("not configured"));
    expect(out.status).toBe("failed");
    expect(out.result).toBeNull();
    expect(out.error).toEqual({ message: "not configured", code: "issuer_not_configured" });
  });

  it("handles a plain error without a code", () => {
    const out = toError(new Error("boom"));
    expect(out.error).toEqual({ message: "boom" });
  });
});
