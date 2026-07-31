import type { ExecutionMetadata, StepResult } from "@skills-mobility/contracts";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { DeliveredDetailCard } from "./DeliveredDetailCard";

const baseExecution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  decisions: [],
  plan_id: "phase1-skill_mastered.v1",
  steps: [],
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

function deliveryStep(actionId: string): StepResult {
  return {
    step_id: 8,
    action_id: actionId,
    status: "succeeded",
    attempt: 1,
    output: {},
    error: null,
    started_at: "2026-07-09T00:00:02Z",
    finished_at: "2026-07-09T00:00:03Z",
  };
}

describe("DeliveredDetailCard", () => {
  afterEach(() => {
    cleanup();
  });

  test("shows the real recipient when present on the execution's result", () => {
    render(
      <DeliveredDetailCard
        execution={{ ...baseExecution, result: { recipient_profile_id: "@smi-demo-learner" } }}
      />,
    );
    expect(screen.getByText("@smi-demo-learner")).toBeTruthy();
  });

  test("falls back to unknown when the result has no recipient", () => {
    render(<DeliveredDetailCard execution={baseExecution} />);
    const recipientValue = screen.getByText("recipient").closest("li")?.querySelector(".mono");
    expect(recipientValue?.textContent).toBe("unknown");
  });

  test("discloses that the delivery confirmation itself is mocked", () => {
    render(<DeliveredDetailCard execution={baseExecution} />);
    expect(screen.getByText(/no real delivered-confirmation callback/)).toBeTruthy();
  });

  test("names LearnCard Wallet when that's the only delivery that succeeded", () => {
    render(
      <DeliveredDetailCard
        execution={{ ...baseExecution, steps: [deliveryStep("deliver_to_learncard_wallet")] }}
      />,
    );
    expect(screen.getByText("LearnCard Wallet")).toBeTruthy();
  });

  test("names SmartResume when that's the only delivery that succeeded", () => {
    render(
      <DeliveredDetailCard
        execution={{ ...baseExecution, steps: [deliveryStep("deliver_to_smartresume")] }}
      />,
    );
    expect(screen.getByText("SmartResume")).toBeTruthy();
  });

  test("names both targets when a single execution delivered to LearnCard Wallet and SmartResume", () => {
    render(
      <DeliveredDetailCard
        execution={{
          ...baseExecution,
          steps: [deliveryStep("deliver_to_learncard_wallet"), deliveryStep("deliver_to_smartresume")],
        }}
      />,
    );
    expect(screen.getByText("LearnCard Wallet, SmartResume")).toBeTruthy();
  });

  test("falls back to unknown when no delivery step succeeded", () => {
    render(
      <DeliveredDetailCard
        execution={{
          ...baseExecution,
          steps: [{ ...deliveryStep("deliver_to_learncard_wallet"), status: "failed" }],
        }}
      />,
    );
    const deliveredToValue = screen.getByText("delivered to").closest("li")?.querySelector(".mono");
    expect(deliveredToValue?.textContent).toBe("unknown");
  });
});
