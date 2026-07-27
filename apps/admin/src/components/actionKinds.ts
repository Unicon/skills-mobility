// 3 of 8 Phase-1 actions route through the LLM Decision Service seam (Field
// Mapping / Field Synthesis), per services/orchestrator/src/orchestrator/actions.py::ACTIONS.
const AI_BACKED_ACTIONS = new Set([
  "generate_issuer_payload_mapping",
  "generate_issuer_payload_synthesis",
  "generate_wallet_payload_mapping",
]);

export function isAiBackedAction(actionId: string): boolean {
  return AI_BACKED_ACTIONS.has(actionId);
}
