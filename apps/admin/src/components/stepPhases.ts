import type { DecisionKind } from "@skills-mobility/contracts";
import { KIND_LABEL } from "./decisionKinds";

// The four decision-node kinds + the two bookends. Cross-highlight state holds one
// of these or null; a step highlights when its phase === the active phase.
// Equals NonNullable<ExpandedKey>, DecisionFlow's node-key domain — keep one definition.
export type Phase = DecisionKind | "event" | "delivered";

// action_id → governing pipeline phase. DISPLAY concern (action_id is a bare string
// in StepResult, not a backend Literal). Verified live against the demo/e2e-aligned
// integration branch (main + #77/#78/#85/#87/#88/#89/#90/#102/#105) — fired
// ACCY-111-grade-m1 (LearnCard Wallet path) and FINC-106-grade-m1 (SmartResume path)
// through a real orchestrator and read the resulting steps[] back.
// field_mapping = the transformation passes (mapping -> synthesis -> translation,
// ADR-0017's per-phase pattern), now three phases: credential_template (always),
// then issuer (always), then exactly one of wallet/smartresume depending on the
// selected delivery target. wallet/smartresume skip synthesis (same as Phase 1).
// workflow_actions_plan = orchestration actions (resolve recipient, issue badge).
// delivered = terminal delivery — LearnCard Wallet and/or SmartResume; a single
// execution can hit both (FR-P2-7), matching DecisionFlow's generic `delivered` signal.
// gate/delivery_targets/event govern no steps. Unlisted action_id -> null (graceful).
// Typed Record<string, Phase> (NOT a closed literal) so stepPhase can index it with
// an arbitrary action_id under TS strict without a cast; a miss is undefined -> null.
export const STEP_PHASE: Record<string, Phase> = {
  resolve_learncard_profile: "workflow_actions_plan",
  generate_credential_template_mapping: "field_mapping",
  generate_credential_template_synthesis: "field_mapping",
  execute_credential_template_translation: "field_mapping",
  generate_issuer_payload_mapping: "field_mapping",
  generate_issuer_payload_synthesis: "field_mapping",
  execute_issuer_payload_translation: "field_mapping",
  issue_learncard_badge: "workflow_actions_plan",
  generate_learncard_wallet_payload_mapping: "field_mapping",
  execute_learncard_wallet_payload_translation: "field_mapping",
  deliver_to_learncard_wallet: "delivered",
  generate_smartresume_payload_mapping: "field_mapping",
  execute_smartresume_payload_translation: "field_mapping",
  deliver_to_smartresume: "delivered",
};

export function stepPhase(actionId: string): Phase | null {
  return STEP_PHASE[actionId] ?? null;
}

export const PHASE_LABEL: Record<Phase, string> = {
  ...KIND_LABEL,
  event: "event",
  delivered: "delivered",
};
