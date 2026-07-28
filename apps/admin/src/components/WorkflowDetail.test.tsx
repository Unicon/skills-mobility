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

  test("hovering the field mapping node highlights exactly its transformation step rows", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    fireEvent.mouseEnter(screen.getByRole("button", { name: "field mapping" }));

    const highlightedActionIds = happyPathExecution.steps
      .filter((s) => screen.getByText(s.action_id).closest("button")?.className.includes("highlighted"))
      .map((s) => s.action_id);

    const expectedFieldMappingActionIds = Object.keys(STEP_PHASE).filter(
      (actionId) => STEP_PHASE[actionId] === "field_mapping",
    );

    expect(highlightedActionIds.sort()).toEqual(expectedFieldMappingActionIds.sort());
  });

  test("hovering a transformation step row highlights the field mapping node", () => {
    mockedUseExecution.mockReturnValue({ execution: happyPathExecution, error: null });
    render(<WorkflowDetail executionId="exec_1" onBack={() => {}} />);

    fireEvent.mouseEnter(
      screen.getByText("generate_issuer_payload_mapping").closest("button")!,
    );

    expect(screen.getByRole("button", { name: "field mapping" }).className).toContain(
      "decision-node-highlighted",
    );
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
    fireEvent.mouseEnter(screen.getByRole("button", { name: "field mapping" }));
    expect(screen.queryByText(/Dashed phases run deterministically/)).toBeNull();
  });
});
