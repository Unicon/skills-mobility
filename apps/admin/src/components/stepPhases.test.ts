import { describe, expect, test } from "vitest";
import { isAiBackedAction } from "./actionKinds";
import { PHASE_LABEL, STEP_PHASE, stepPhase } from "./stepPhases";

describe("stepPhase", () => {
  test.each([
    ["resolve_learncard_profile", "workflow_actions_plan"],
    ["generate_credential_template_mapping", "field_mapping"],
    ["generate_credential_template_synthesis", "field_mapping"],
    ["execute_credential_template_translation", "field_mapping"],
    ["generate_issuer_payload_mapping", "field_mapping"],
    ["generate_issuer_payload_synthesis", "field_mapping"],
    ["execute_issuer_payload_translation", "field_mapping"],
    ["issue_learncard_badge", "workflow_actions_plan"],
    ["generate_learncard_wallet_payload_mapping", "field_mapping"],
    ["execute_learncard_wallet_payload_translation", "field_mapping"],
    ["deliver_to_learncard_wallet", "delivered"],
    ["generate_smartresume_payload_mapping", "field_mapping"],
    ["execute_smartresume_payload_translation", "field_mapping"],
    ["deliver_to_smartresume", "delivered"],
  ])("maps %s to %s", (actionId, expectedPhase) => {
    expect(stepPhase(actionId)).toBe(expectedPhase);
  });

  test("returns null for an unknown action_id", () => {
    expect(stepPhase("some_future_action")).toBeNull();
  });

  test("the ten transformation steps (credential_template + issuer + wallet + smartresume) all map to field_mapping", () => {
    const transformationSteps = [
      "generate_credential_template_mapping",
      "generate_credential_template_synthesis",
      "execute_credential_template_translation",
      "generate_issuer_payload_mapping",
      "generate_issuer_payload_synthesis",
      "execute_issuer_payload_translation",
      "generate_learncard_wallet_payload_mapping",
      "execute_learncard_wallet_payload_translation",
      "generate_smartresume_payload_mapping",
      "execute_smartresume_payload_translation",
    ];
    for (const actionId of transformationSteps) {
      expect(stepPhase(actionId)).toBe("field_mapping");
    }
  });

  test("PHASE_LABEL covers every Phase, including the two bookends", () => {
    expect(PHASE_LABEL.gate).toBe("gate");
    expect(PHASE_LABEL.delivery_targets).toBe("delivery targets");
    expect(PHASE_LABEL.workflow_actions_plan).toBe("workflow actions");
    expect(PHASE_LABEL.field_mapping).toBe("field mapping");
    expect(PHASE_LABEL.event).toBe("event");
    expect(PHASE_LABEL.delivered).toBe("delivered");
  });

  test("both delivery actions (LearnCard Wallet and SmartResume) map to the same delivered phase", () => {
    expect(stepPhase("deliver_to_learncard_wallet")).toBe("delivered");
    expect(stepPhase("deliver_to_smartresume")).toBe("delivered");
  });

  test("the AI-backed set is a strict subset of the field_mapping-phase set", () => {
    const fieldMappingActions = Object.keys(STEP_PHASE).filter(
      (actionId) => STEP_PHASE[actionId] === "field_mapping",
    );
    const aiActions = fieldMappingActions.filter(isAiBackedAction);
    expect(aiActions.length).toBe(6);
    expect(fieldMappingActions.length).toBe(10);
    for (const actionId of aiActions) {
      expect(fieldMappingActions).toContain(actionId);
    }
  });
});
