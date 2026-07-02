import { type IssuanceResult } from "./learncard";
import { type IssueResponse } from "./schemas";

// Normalize LearnCard SDK results + errors into the adapter response shape
// (design §3 `resultmap/`, §4 step 8). Keeps router-facing output stable as the
// SDK's own shapes change.

export function toSuccess(result: IssuanceResult): IssueResponse {
  return {
    status: "succeeded",
    external_reference_id: result.externalReferenceId,
    result: { issued_credential: result.issuedCredential },
    error: null,
  };
}

export function toError(err: unknown): IssueResponse {
  const message = err instanceof Error ? err.message : String(err);
  const code =
    typeof err === "object" && err !== null && "code" in err
      ? String((err as { code: unknown }).code)
      : undefined;
  return {
    status: "failed",
    external_reference_id: null,
    result: null,
    error: code ? { message, code } : { message },
  };
}
