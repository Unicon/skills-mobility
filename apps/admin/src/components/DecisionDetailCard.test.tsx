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
  plan_source: "llm",
  issuer_omitted_from_selection: false,
  created_at: "2026-07-09T00:00:01Z",
};

describe("DecisionDetailCard", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders the Instructions bubble with the goal and a JSON block of the mock input", () => {
    render(<DecisionDetailCard decision={gateDecision} execution={execution} />);
    expect(screen.getByText(/Instructions/)).toBeTruthy();
    expect(screen.getByText(/proceed to delivery-target selection/)).toBeTruthy();
    expect(screen.getByText(/execution_id/)).toBeTruthy();
  });

  test("Instructions bubble discloses it's reconstructed, not real backend data", () => {
    render(<DecisionDetailCard decision={gateDecision} execution={execution} />);
    expect(screen.getByText("reconstructed")).toBeTruthy();
    expect(screen.getByText(/doesn.t persist the real input/)).toBeTruthy();
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

  test("plan_source: 'llm' renders the normal LLM-voice narrative with no fallback badge", () => {
    render(<DecisionDetailCard decision={deliveryTargetsDecision} execution={execution} />);
    expect(screen.getByText(/I went with targets selected/)).toBeTruthy();
    expect(screen.queryByText("deterministic fallback")).toBeNull();
  });

  test("plan_source: null (predates the field) renders exactly like today — no badge, normal narrative", () => {
    render(<DecisionDetailCard decision={gateDecision} execution={execution} />);
    expect(screen.queryByText("deterministic fallback")).toBeNull();
    expect(screen.getByText(/I went with continue to delivery targets/)).toBeTruthy();
  });

  test("plan_source: 'deterministic_fallback' shows a badge and a plain, non-fabricated narrative", () => {
    const fallbackDecision: DecisionArtifact = { ...gateDecision, plan_source: "deterministic_fallback" };
    render(<DecisionDetailCard decision={fallbackDecision} execution={execution} />);
    expect(screen.getByText("deterministic fallback")).toBeTruthy();
    const responseText = screen.getByText(/orchestrator's deterministic fallback produced this decision/);
    expect(responseText.textContent).not.toContain("I went with");
    expect(responseText.textContent).not.toContain("confident");
    expect(responseText.textContent).toContain("continue to delivery targets");
    expect(responseText.textContent).toContain("Deterministic Phase 1 happy-path gate decision");
  });

  test("issuer_omitted_from_selection shows a distinct alert, separate from the fallback badge", () => {
    const omittedDecision: DecisionArtifact = {
      ...deliveryTargetsDecision,
      issuer_omitted_from_selection: true,
    };
    render(<DecisionDetailCard decision={omittedDecision} execution={execution} />);
    expect(screen.getByText(/omitted the LearnCard issuer/)).toBeTruthy();
    expect(screen.queryByText("deterministic fallback")).toBeNull();
  });

  test("plan_source: 'llm' and issuer_omitted_from_selection together both render, without contradiction", () => {
    const bothDecision: DecisionArtifact = {
      ...deliveryTargetsDecision,
      plan_source: "llm",
      issuer_omitted_from_selection: true,
    };
    render(<DecisionDetailCard decision={bothDecision} execution={execution} />);
    expect(screen.getByText(/omitted the LearnCard issuer/)).toBeTruthy();
    expect(screen.getByText(/I went with targets selected/)).toBeTruthy();
    expect(screen.queryByText("deterministic fallback")).toBeNull();
  });
});
