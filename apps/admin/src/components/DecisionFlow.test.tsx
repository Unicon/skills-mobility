import type { DecisionArtifact, ExecutionMetadata, StepResult } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, test } from "vitest";
import { DecisionFlow } from "./DecisionFlow";
import type { Phase } from "./stepPhases";

// DecisionFlow's selection is now controlled (mirrors WorkflowDetail's own
// lifted state) — this wrapper gives clicks somewhere to actually persist to.
function ControlledDecisionFlow(
  props: Omit<Parameters<typeof DecisionFlow>[0], "selectedPhase" | "onSelectedPhaseChange">,
) {
  const [selectedPhase, setSelectedPhase] = useState<Phase | null>(null);
  return <DecisionFlow {...props} selectedPhase={selectedPhase} onSelectedPhaseChange={setSelectedPhase} />;
}

const gateDecision: DecisionArtifact = {
  kind: "gate",
  confidence: 1,
  rationale: "Deterministic Phase 1 happy-path gate decision.",
  outcome: "continue_to_delivery_targets",
  candidates: [],
  artifact_ref: null,
  invocation_log_ref: null,
  plan_source: null,
  issuer_omitted_from_selection: false,
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
  plan_source: "llm",
  issuer_omitted_from_selection: false,
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

const smartResumeDeliveredStep: StepResult = {
  ...deliveredStep,
  step_id: 9,
  action_id: "deliver_to_smartresume",
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
    render(<ControlledDecisionFlow execution={baseExecution} activePhase={null} onActivePhaseChange={() => {}} />);
    const button = screen.getByRole("button", { name: "gate" });
    expect(button.className).toContain("decision-node-pending");
  });

  test("always renders a populated Event node and a pending Delivered node when nothing was delivered", () => {
    render(<ControlledDecisionFlow execution={baseExecution} activePhase={null} onActivePhaseChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Event" }).className).toContain("decision-node-populated");
    expect(screen.getByRole("button", { name: "Delivered" }).className).toContain("decision-node-pending");
  });

  test("renders a populated Delivered node once the LearnCard Wallet delivery step succeeded", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, steps: [deliveredStep] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Delivered" }).className).toContain("decision-node-populated");
  });

  test("renders a populated Delivered node once the SmartResume delivery step succeeded (no LearnCard wallet delivery)", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, steps: [smartResumeDeliveredStep] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Delivered" }).className).toContain("decision-node-populated");
  });

  test("expanding Event shows the reconstructed envelope; expanding Delivered is a no-op while pending", () => {
    render(<ControlledDecisionFlow execution={baseExecution} activePhase={null} onActivePhaseChange={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Event" }));
    expect(screen.getByText(/skill_mastered/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Delivered" }));
    expect(screen.getByRole("button", { name: "Delivered" }).getAttribute("aria-expanded")).toBe("false");
  });

  test("expanding a populated Delivered node shows the mocked delivery confirmation", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, steps: [deliveredStep] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Delivered" }));
    expect(screen.getByText(/no real delivered-confirmation callback/)).toBeTruthy();
  });

  test("expanding a Delivered node fed by both targets names both in the confirmation", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, steps: [deliveredStep, smartResumeDeliveredStep] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Delivered" }));
    expect(screen.getByText("LearnCard Wallet, SmartResume")).toBeTruthy();
  });

  test("renders today's real shape: gate populated, the rest pending", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "gate" }).className).toContain(
      "decision-node-populated",
    );
    expect(screen.getByRole("button", { name: "delivery targets" }).className).toContain(
      "decision-node-pending",
    );
    expect(screen.getByRole("button", { name: "workflow actions" }).className).toContain(
      "decision-node-pending",
    );
  });

  test("expanding a populated node shows rejected candidates dimmed and the selected one marked", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision, deliveryTargetsDecision] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "delivery targets" }));

    const selected = screen.getByText("learncard_wallet").closest("li");
    const rejected = screen.getByText("smartresume").closest("li");
    expect(selected?.className).toBe("decision-candidate-selected");
    expect(rejected?.className).toBe("decision-candidate-rejected");
  });

  test("clicking a pending node is a no-op: no aria-expanded flip, no card, no state cleared", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "gate" }));
    expect(screen.getByText("gate Response")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "delivery targets" }));

    expect(screen.getByRole("button", { name: "delivery targets" }).getAttribute("aria-expanded")).toBe(
      "false",
    );
    // The gate's detail card is still showing — clicking a pending node didn't clear it.
    expect(screen.getByText("gate Response")).toBeTruthy();
  });

  test("renders the decision nodes in gate → delivery targets → workflow actions order", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision, deliveryTargetsDecision] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    const labels = screen
      .getAllByRole("button")
      .map((button) => button.getAttribute("aria-label"))
      .filter((label): label is string => label != null && label !== "Event" && label !== "Delivered");
    expect(labels).toEqual(["gate", "delivery targets", "workflow actions"]);
  });

  test("shows the dashed-phase legend once at least one step has run", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision], steps: [deliveredStep] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    expect(screen.getByText(/Dashed phases run deterministically/)).toBeTruthy();
  });

  test("hides the legend for the single-pending-gate fallback (decisions empty)", () => {
    render(<ControlledDecisionFlow execution={baseExecution} activePhase={null} onActivePhaseChange={() => {}} />);
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });

  test("hides the legend for a gate-terminated run (decisions:[gate], steps:[])", () => {
    render(
      <ControlledDecisionFlow
        execution={{ ...baseExecution, decisions: [gateDecision], steps: [] }}
        activePhase={null}
        onActivePhaseChange={() => {}}
      />,
    );
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });
});
