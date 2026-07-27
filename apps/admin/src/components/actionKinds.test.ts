import { describe, expect, test } from "vitest";
import { isAiBackedAction } from "./actionKinds";

describe("isAiBackedAction", () => {
  test.each([
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "generate_wallet_payload_mapping",
  ])("returns true for the AI-backed action %s", (actionId) => {
    expect(isAiBackedAction(actionId)).toBe(true);
  });

  test.each([
    "resolve_learncard_profile",
    "execute_issuer_payload_translation",
    "issue_learncard_badge",
    "execute_wallet_payload_translation",
    "deliver_to_learncard_wallet",
  ])("returns false for the deterministic action %s", (actionId) => {
    expect(isAiBackedAction(actionId)).toBe(false);
  });

  test("returns false for an unknown action_id", () => {
    expect(isAiBackedAction("some_future_action")).toBe(false);
  });
});
