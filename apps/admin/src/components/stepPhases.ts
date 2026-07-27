import type { DecisionKind } from "@skills-mobility/contracts";
import { KIND_LABEL } from "./decisionKinds";

// The four decision-node kinds + the two bookends. Cross-highlight state holds one
// of these or null; a step highlights when its phase === the active phase.
// Equals NonNullable<ExpandedKey>, DecisionFlow's node-key domain — keep one definition.
export type Phase = DecisionKind | "event" | "delivered";

// action_id → governing pipeline phase. DISPLAY concern (action_id is a bare string
// in StepResult, not a backend Literal), mirrored from
// services/orchestrator/src/orchestrator/planner.py::_phase1_steps + actions.py::ACTIONS.
// field_mapping = the transformation passes (runs twice today — issuer 2-4, wallet 6-7;
// PR #89/#90 (unmerged) make the plan target-aware/composable, so this can grow).
// workflow_actions_plan = orchestration actions (resolve recipient, issue badge).
// delivered = terminal delivery to any target — LearnCard Wallet today, and
// SmartResume once PR #89 (unmerged) lands its `deliver_to_smartresume` action;
// matches DecisionFlow's generic `delivered` signal (FR-P2-7: both can succeed
// in one execution).
// gate/delivery_targets/event govern no steps. Unlisted action_id → null (graceful).
// Typed Record<string, Phase> (NOT a closed 8-key literal) so stepPhase can index it
// with an arbitrary action_id under TS strict without a cast; a miss is undefined → null.
export const STEP_PHASE: Record<string, Phase> = {
  resolve_learncard_profile: "workflow_actions_plan",
  generate_issuer_payload_mapping: "field_mapping",
  generate_issuer_payload_synthesis: "field_mapping",
  execute_issuer_payload_translation: "field_mapping",
  issue_learncard_badge: "workflow_actions_plan",
  generate_wallet_payload_mapping: "field_mapping",
  execute_wallet_payload_translation: "field_mapping",
  deliver_to_learncard_wallet: "delivered",
  // Not yet on main — from PR #89 (feat/orchestrator-target-aware-plan, unmerged).
  // Stubbed ahead of merge so a SmartResume-only delivery doesn't silently fall
  // through as an untagged, unhighlighted step.
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
