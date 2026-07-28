// 6 of 14 actions route through an LLM Decision Service seam (Field Mapping /
// Field Synthesis) — one mapping+synthesis pair per transformation phase that has
// synthesis (credential_template, issuer), plus a mapping-only seam for whichever
// delivery branch ran (wallet or smartresume; neither has a synthesis step).
// Verified live against the demo/e2e-aligned integration branch (main +
// #77/#78/#85/#87/#88/#89/#90/#102/#105).
const AI_BACKED_ACTIONS = new Set([
  "generate_credential_template_mapping",
  "generate_credential_template_synthesis",
  "generate_issuer_payload_mapping",
  "generate_issuer_payload_synthesis",
  "generate_learncard_wallet_payload_mapping",
  "generate_smartresume_payload_mapping",
]);

export function isAiBackedAction(actionId: string): boolean {
  return AI_BACKED_ACTIONS.has(actionId);
}
