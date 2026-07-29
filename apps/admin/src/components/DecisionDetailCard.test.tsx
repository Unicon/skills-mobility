import type { DecisionArtifact, ExecutionMetadata } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { DecisionDetailCard } from "./DecisionDetailCard";

const execution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "course_completed",
  status: "completed",
  decisions: [],
  plan_id: "phase1-course_completed.v1",
  steps: [],
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

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
    { label: "smartresume", confidence: 0.31, rationale: "Low fit", selected: false },
    { label: "learncard_wallet", confidence: 0.82, rationale: "Best fit", selected: true },
  ],
  artifact_ref: "s3://artifacts/delivery-targets/1",
  invocation_log_ref: "log://invocations/1",
  plan_source: null,
  issuer_omitted_from_selection: false,
  created_at: "2026-07-09T00:00:01Z",
};

describe("DecisionDetailCard", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders the Instructions bubble with the goal and a JSON block of the mock input", () => {
    render(<DecisionDetailCard decision={gateDecision} execution={execution} />);
    expect(screen.getByText("Instructions")).toBeTruthy();
    expect(screen.getByText(/proceed to delivery-target selection/)).toBeTruthy();
    expect(screen.getByText(/execution_id/)).toBeTruthy();
  });

  test("renders the Response bubble narrating outcome, confidence, and rationale, with no candidate list", () => {
    render(<DecisionDetailCard decision={gateDecision} execution={execution} />);
    expect(screen.getByText("gate Response")).toBeTruthy();
    const responseText = screen.getByText(/I went with continue to delivery targets/);
    expect(responseText.textContent).toContain("100% confident");
    expect(responseText.textContent).toContain("deterministic Phase 1 happy-path gate decision");
    expect(screen.queryByRole("list")).toBeNull();
  });

  test("mentions the number of other candidates weighed in the response prose", () => {
    render(<DecisionDetailCard decision={deliveryTargetsDecision} execution={execution} />);
    expect(screen.getByText(/I weighed this against 1 other option/)).toBeTruthy();
  });

  test("sorts candidates by confidence descending regardless of input order", () => {
    const { container } = render(
      <DecisionDetailCard decision={deliveryTargetsDecision} execution={execution} />,
    );
    const labels = Array.from(container.querySelectorAll(".decision-candidate-label")).map(
      (el) => el.textContent,
    );
    expect(labels).toEqual(["learncard_wallet", "smartresume"]);
  });

  test("shows the raw artifact/invocation refs only after clicking 'View raw'", () => {
    render(<DecisionDetailCard decision={deliveryTargetsDecision} execution={execution} />);
    expect(screen.queryByText(/s3:\/\/artifacts/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View raw" }));
    expect(screen.getByText(/s3:\/\/artifacts/)).toBeTruthy();
  });
});
