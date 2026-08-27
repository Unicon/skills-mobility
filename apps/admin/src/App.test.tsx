import type { ExecutionMetadata, ExecutionSummary } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import App from "./App";

vi.mock("@skills-mobility/contracts", () => ({
  orchestratorApi: {
    getExecution: vi.fn(),
    listExecutions: vi.fn(),
  },
}));

const listedExecution: ExecutionSummary = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  step_progress: { completed: 1, total: 1 },
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

const fullExecution: ExecutionMetadata = {
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

describe("App routing", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("renders the execution list at the root path", async () => {
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([listedExecution]);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("button", { name: "Open workflow exec_1" })).toBeTruthy();
  });

  test("shows the demo warm-up reminder", async () => {
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([listedExecution]);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/fire two warm-up events before presenting/i)).toBeTruthy();
  });

  test("clicking a row navigates to its execution's detail route", async () => {
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([listedExecution]);
    vi.mocked(orchestratorApi.getExecution).mockResolvedValue(fullExecution);
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByRole("button", { name: "Open workflow exec_1" }));

    expect(await screen.findByText("← Back to list")).toBeTruthy();
    expect(orchestratorApi.getExecution).toHaveBeenCalledWith("exec_1");
  });

  test("deep-links directly to an execution's detail route without visiting the list first", async () => {
    vi.mocked(orchestratorApi.getExecution).mockResolvedValue(fullExecution);
    render(
      <MemoryRouter initialEntries={["/executions/exec_1"]}>
        <App />
      </MemoryRouter>,
    );

    expect(await screen.findByText("← Back to list")).toBeTruthy();
    expect(orchestratorApi.getExecution).toHaveBeenCalledWith("exec_1");
    expect(orchestratorApi.listExecutions).not.toHaveBeenCalled();
  });

  test("Back to list navigates from the detail route back to the root path", async () => {
    vi.mocked(orchestratorApi.getExecution).mockResolvedValue(fullExecution);
    vi.mocked(orchestratorApi.listExecutions).mockResolvedValue([listedExecution]);
    render(
      <MemoryRouter initialEntries={["/executions/exec_1"]}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByText("← Back to list"));

    expect(await screen.findByRole("button", { name: "Open workflow exec_1" })).toBeTruthy();
  });
});
