import { describe, expect, test } from "vitest";
import { isAiBackedAction } from "./actionKinds";

describe("isAiBackedAction", () => {
  test.each([
    "generate_credential_template_mapping",
    "generate_credential_template_synthesis",
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "generate_learncard_wallet_payload_mapping",
    "generate_smartresume_payload_mapping",
  ])("returns true for the AI-backed action %s", (actionId) => {
    expect(isAiBackedAction(actionId)).toBe(true);
  });

  test.each([
    "resolve_learncard_profile",
    "execute_credential_template_translation",
    "execute_issuer_payload_translation",
    "issue_learncard_badge",
    "execute_learncard_wallet_payload_translation",
    "execute_smartresume_payload_translation",
    "deliver_to_learncard_wallet",
    "deliver_to_smartresume",
  ])("returns false for the deterministic action %s", (actionId) => {
    expect(isAiBackedAction(actionId)).toBe(false);
  });

  test("returns false for an unknown action_id", () => {
    expect(isAiBackedAction("some_future_action")).toBe(false);
  });
});
