import type { DecisionKind } from "@skills-mobility/contracts";

export const KIND_ORDER: DecisionKind[] = [
  "gate",
  "delivery_targets",
  "field_mapping",
  "workflow_actions_plan",
];

export const KIND_LABEL: Record<DecisionKind, string> = {
  gate: "gate",
  delivery_targets: "delivery targets",
  field_mapping: "field mapping",
  workflow_actions_plan: "workflow actions",
};
