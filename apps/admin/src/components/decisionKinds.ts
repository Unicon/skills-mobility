import type { DecisionKind } from "@skills-mobility/contracts";

export const KIND_ORDER: DecisionKind[] = [
  "gate",
  "delivery_targets",
  "workflow_actions_plan",
  "field_mapping",
];

export const KIND_LABEL: Record<DecisionKind, string> = {
  gate: "gate",
  delivery_targets: "delivery targets",
  field_mapping: "field mapping",
  workflow_actions_plan: "workflow actions",
};
