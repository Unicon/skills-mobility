import type { ExecutionMetadata, StepResult } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { useExecution } from "../hooks/useExecution";
import { STEP_PHASE } from "./stepPhases";
import { WorkflowDetail } from "./WorkflowDetail";

vi.mock("../hooks/useExecution", () => ({
  useExecution: vi.fn(),
}));

const mockedUseExecution = vi.mocked(useExecution);

const phase1ActionIds = Object.keys(STEP_PHASE);

function stepFor(actionId: string, index: number): StepResult {
  return {
    step_id: index + 1,
    action_id: actionId,
    status: "succeeded",
    attempt: 1,
    output: {},
    error: null,
    started_at: `2026-07-09T00:00:0${index}Z`,
    finished_at: `2026-07-09T00:00:0${index + 1}Z`,
  };
}

const happyPathExecution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  decisions: [
    {
      kind: "gate",
      confidence: 1,
      rationale: "Deterministic Phase 1 happy-path gate decision.",
      outcome: "continue_to_delivery_targets",
      candidates: [],
      artifact_ref: null,
      invocation_log_ref: null,
      decision_source: "llm",
      created_at: "2026-07-09T00:00:00Z",
    },
    {
      kind: "delivery_targets",
      confidence: 0.82,
      rationale: "Selected the LearnCard wallet as the highest-confidence target.",
      outcome: "targets_selected",
      candidates: [],
      artifact_ref: null,
      invocation_log_ref: null,
      decision_source: "llm",
      created_at: "2026-07-09T00:00:00Z",
    },
    {
      kind: "workflow_actions_plan",
      confidence: 1,
      rationale: "Deterministic Phase 1 LearnCard workflow.",
      outcome: "plan_generated",
      candidates: [],
      artifact_ref: null,
      invocation_log_ref: null,
      decision_source: "llm",
      created_at: "2026-07-09T00:00:00Z",
    },
  ],
  plan_id: "phase1-skill_mastered.v1",
  steps: phase1ActionIds.map(stepFor),
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

describe("WorkflowDetail", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("hovering a transformation step row highlights every step row sharing its phase", () => {
    // field_mapping has no pipeline node (decisionKinds.ts — it's never a real
    // DecisionArtifact today, and the real steps run in two separate windows
    // anyway), so this cross-highlight now only ever happens row-to-row.
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    fireEvent.mouseEnter(screen.getByText("generate_issuer_payload_mapping").closest("button")!);

    const highlightedActionIds = happyPathExecution.steps
      .filter((s) => screen.getByText(s.action_id).closest("button")?.className.includes("highlighted"))
      .map((s) => s.action_id);

    const expectedFieldMappingActionIds = Object.keys(STEP_PHASE).filter(
      (actionId) => STEP_PHASE[actionId] === "field_mapping",
    );

    expect(highlightedActionIds.sort()).toEqual(expectedFieldMappingActionIds.sort());
  });

  test("clicking the (populated) workflow actions node marks its steps 'selected' and persists after the mouse leaves", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    const node = screen.getByRole("button", { name: "workflow actions" });
    fireEvent.mouseEnter(node);
    fireEvent.click(node);
    fireEvent.mouseLeave(node);

    const selectedActionIds = happyPathExecution.steps
      .filter((s) => screen.getByText(s.action_id).closest("button")?.className.includes("selected"))
      .map((s) => s.action_id);
    const expectedWorkflowActionsActionIds = Object.keys(STEP_PHASE).filter(
      (actionId) => STEP_PHASE[actionId] === "workflow_actions_plan",
    );

    expect(selectedActionIds.sort()).toEqual(expectedWorkflowActionsActionIds.sort());
    // Hover already left, so none of those rows should also read as "highlighted".
    const anyHighlighted = happyPathExecution.steps.some((s) =>
      screen.getByText(s.action_id).closest("button")?.className.includes("highlighted"),
    );
    expect(anyHighlighted).toBe(false);
  });

  test("hovering a step row of a different phase while a node is selected shows both distinctly", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "workflow actions" }));
    fireEvent.mouseEnter(screen.getByText("generate_issuer_payload_mapping").closest("button")!);

    const workflowActionsStep = screen.getByText("resolve_learncard_profile").closest("button");
    const fieldMappingStep = screen.getByText("generate_issuer_payload_mapping").closest("button");

    expect(workflowActionsStep?.className).toContain("selected");
    expect(workflowActionsStep?.className).not.toContain("highlighted");
    expect(fieldMappingStep?.className).toContain("highlighted");
    expect(fieldMappingStep?.className).not.toContain("selected");
  });

  test("collapsing the selected node clears 'selected' from its steps", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    const node = screen.getByRole("button", { name: "workflow actions" });
    fireEvent.click(node);
    fireEvent.click(node); // collapse

    const anySelected = happyPathExecution.steps.some((s) =>
      screen.getByText(s.action_id).closest("button")?.className.includes("selected"),
    );
    expect(anySelected).toBe(false);
  });

  test("hovering the gate node highlights no step rows", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    fireEvent.mouseEnter(screen.getByRole("button", { name: "gate" }));

    const anyHighlighted = happyPathExecution.steps.some((s) =>
      screen.getByText(s.action_id).closest("button")?.className.includes("highlighted"),
    );
    expect(anyHighlighted).toBe(false);
  });

  test("error state: renders the unreachable-API message with no pipeline, legend, or phase tags", () => {
    mockedUseExecution.mockReturnValue({ execution: null, error: new Error("boom") });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    expect(screen.getByText("Unable to reach the Orchestrator read API.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "gate" })).toBeNull();
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });

  test("loading state: renders Loading… with no pipeline, legend, or phase tags", () => {
    mockedUseExecution.mockReturnValue({ execution: null, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    expect(screen.getByText("Loading…")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "gate" })).toBeNull();
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });

  test("steps-empty state: renders the placeholder and hovering a node highlights nothing", () => {
    mockedUseExecution.mockReturnValue({
      execution: { ...happyPathExecution, steps: [] },
      error: null,
    });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    expect(screen.getByText("No steps recorded yet.")).toBeTruthy();
    fireEvent.mouseEnter(screen.getByRole("button", { name: "gate" }));
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });
});
