import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { WalletDetailCard } from "./WalletDetailCard";

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

describe("WalletDetailCard", () => {
  afterEach(() => {
    cleanup();
  });

  test("shows the real recipient when present on the execution's result", () => {
    render(<WalletDetailCard execution={{ ...baseExecution, result: { recipient_profile_id: "@smi-demo-learner" } }} />);
    expect(screen.getByText("@smi-demo-learner")).toBeTruthy();
  });

  test("falls back to unknown when the result has no recipient", () => {
    render(<WalletDetailCard execution={baseExecution} />);
    expect(screen.getByText("unknown")).toBeTruthy();
  });

  test("discloses that the delivery confirmation itself is mocked", () => {
    render(<WalletDetailCard execution={baseExecution} />);
    expect(screen.getByText(/no real wallet delivery-confirmation callback/)).toBeTruthy();
  });
});
