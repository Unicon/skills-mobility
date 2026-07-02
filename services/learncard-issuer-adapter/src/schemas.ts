import { z } from "zod";

// Router-facing adapter contract (design §2). The Delivery Router owns the outer
// delivery-action envelope; this is the issuer-adapter-specific shape.
export const IssueRequest = z.object({
  contract_version: z.literal("v1"),
  workflow_id: z.string(),
  execution_id: z.string(),
  step_id: z.string(),
  correlation_id: z.string(),
  delivery_config_ref: z.string(),
  payload: z.object({
    // The unsigned OBv3 the Orchestrator shaped upstream; credentialSubject.id
    // already carries the recipient's LearnCard-resolved DID (Profile Resolver).
    unsigned_vc: z.record(z.unknown()),
  }),
});

export type IssueRequest = z.infer<typeof IssueRequest>;

export interface IssueResponse {
  status: "succeeded" | "failed";
  external_reference_id: string | null;
  result: { issued_credential: Record<string, unknown> } | null;
  error: { message: string; code?: string } | null;
}
