import type { DecisionArtifact, ExecutionMetadata, StepResult } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { DecisionFlow } from "./DecisionFlow";

const gateDecision: DecisionArtifact = {
  kind: "gate",
  confidence: 1,
  rationale: "Deterministic Phase 1 happy-path gate decision.",
  outcome: "continue_to_delivery_targets",
  candidates: [],
  artifact_ref: null,
  invocation_log_ref: null,
  decision_source: null,
  created_at: "2026-07-09T00:00:00Z",
};

const deliveryTargetsDecision: DecisionArtifact = {
  kind: "delivery_targets",
  confidence: 0.82,
  rationale: "Selected the LearnCard wallet as the highest-confidence target.",
  outcome: "targets_selected",
  candidates: [
    { label: "learncard_wallet", confidence: 0.82, rationale: "Best fit", selected: true },
    { label: "smartresume", confidence: 0.31, rationale: "Low fit", selected: false },
  ],
  artifact_ref: "s3://artifacts/delivery-targets/1",
  invocation_log_ref: "log://invocations/1",
  decision_source: null,
  created_at: "2026-07-09T00:00:01Z",
};

const deliveredStep: StepResult = {
  step_id: 8,
  action_id: "deliver_to_learncard_wallet",
  status: "succeeded",
  attempt: 1,
  output: {},
  error: null,
  started_at: "2026-07-09T00:00:02Z",
  finished_at: "2026-07-09T00:00:03Z",
};

const baseExecution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  decisions: [],
  plan_id: null,
  steps: [],
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

describe("DecisionFlow", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders a single pending gate node when decisions is empty", () => {
    render(<DecisionFlow execution={baseExecution} />);
    const button = screen.getByRole("button", { name: "gate" });
    expect(button.className).toContain("decision-node-pending");
  });

  test("always renders a populated Event node and a pending Wallet node when nothing was delivered", () => {
    render(<DecisionFlow execution={baseExecution} />);
    expect(screen.getByRole("button", { name: "Event" }).className).toContain("decision-node-populated");
    expect(screen.getByRole("button", { name: "Wallet" }).className).toContain("decision-node-pending");
  });

  test("renders a populated Wallet node once the delivery step succeeded", () => {
    render(<DecisionFlow execution={{ ...baseExecution, steps: [deliveredStep] }} />);
    expect(screen.getByRole("button", { name: "Wallet" }).className).toContain("decision-node-populated");
  });

  test("expanding Event shows the reconstructed envelope; expanding Wallet is a no-op while pending", () => {
    render(<DecisionFlow execution={baseExecution} />);
    fireEvent.click(screen.getByRole("button", { name: "Event" }));
    expect(screen.getByText(/skill_mastered/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Wallet" }));
    expect(screen.getByRole("button", { name: "Wallet" }).getAttribute("aria-expanded")).toBe("false");
  });

  test("expanding a populated Wallet node shows the mocked delivery confirmation", () => {
    render(<DecisionFlow execution={{ ...baseExecution, steps: [deliveredStep] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Wallet" }));
    expect(screen.getByText(/no real wallet delivery-confirmation callback/)).toBeTruthy();
  });

  test("renders today's real shape: gate populated, the rest pending", () => {
    render(<DecisionFlow execution={{ ...baseExecution, decisions: [gateDecision] }} />);
    expect(screen.getByRole("button", { name: "gate" }).className).toContain(
      "decision-node-populated",
    );
    expect(screen.getByRole("button", { name: "delivery targets" }).className).toContain(
      "decision-node-pending",
    );
    expect(screen.getByRole("button", { name: "field mapping" }).className).toContain(
      "decision-node-pending",
    );
    expect(screen.getByRole("button", { name: "workflow actions" }).className).toContain(
      "decision-node-pending",
    );
  });

  test("expanding a populated node shows rejected candidates dimmed and the selected one marked", () => {
    render(
      <DecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision, deliveryTargetsDecision] }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "delivery targets" }));

    const selected = screen.getByText("learncard_wallet").closest("li");
    const rejected = screen.getByText("smartresume").closest("li");
    expect(selected?.className).toBe("decision-candidate-selected");
    expect(rejected?.className).toBe("decision-candidate-rejected");
  });

  test("clicking a pending node is a no-op: no aria-expanded flip, no card, no state cleared", () => {
    render(<DecisionFlow execution={{ ...baseExecution, decisions: [gateDecision] }} />);
    fireEvent.click(screen.getByRole("button", { name: "gate" }));
    expect(screen.getByText("gate Response")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "field mapping" }));

    expect(screen.getByRole("button", { name: "field mapping" }).getAttribute("aria-expanded")).toBe(
      "false",
    );
    // The gate's detail card is still showing — clicking a pending node didn't clear it.
    expect(screen.getByText("gate Response")).toBeTruthy();
  });
});
