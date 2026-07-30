import type { DecisionKind } from "@skills-mobility/contracts";

// Pipeline-row order. field_mapping is deliberately absent: the Orchestrator
// never records a field_mapping DecisionArtifact today (engine.py only calls
// record_decision for gate/delivery_targets/workflow_actions_plan), so that
// node was permanently pending — and even once it's wired up, the real
// field-mapping steps run in two separate windows interleaved with
// workflow_actions_plan steps (see stepPhases.ts), not once in a fixed slot,
// so a single row position would misrepresent it either way. field_mapping
// stays a valid Phase for step tags/highlighting (STEP_PHASE, KIND_LABEL
// below) — only the aggregate pipeline node is removed.
export const KIND_ORDER: DecisionKind[] = ["gate", "delivery_targets", "workflow_actions_plan"];

export const KIND_LABEL: Record<DecisionKind, string> = {
  gate: "gate",
  delivery_targets: "delivery targets",
  field_mapping: "field mapping",
  workflow_actions_plan: "workflow actions",
};
