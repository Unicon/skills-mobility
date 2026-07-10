import type { ExecutionSummary } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { ExecutionListView } from "./ExecutionListView";

vi.mock("@skills-mobility/contracts", () => ({
  orchestratorApi: {
    getExecution: vi.fn(),
    listExecutions: vi.fn(),
  },
}));

const execution: ExecutionSummary = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  step_progress: { completed: 1, total: 1 },
  created_at: "",
  updated_at: "",
};

describe("ExecutionListView", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("Enter on the correlation-id copy button copies, and does not open the workflow", async () => {
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([execution]);
    const onSelect = vi.fn();

    render(<ExecutionListView onSelect={onSelect} />);

    const copyButton = await screen.findByRole("button", { name: execution.correlation_id });
    copyButton.focus();
    fireEvent.keyDown(copyButton, { key: "Enter" });

    expect(onSelect).not.toHaveBeenCalled();
  });

  test("Enter on the row's open button opens the workflow", async () => {
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([execution]);
    const onSelect = vi.fn();

    render(<ExecutionListView onSelect={onSelect} />);

    const openButton = await screen.findByRole("button", { name: "Open workflow exec_1" });
    fireEvent.click(openButton);

    expect(onSelect).toHaveBeenCalledWith("exec_1");
  });
});
