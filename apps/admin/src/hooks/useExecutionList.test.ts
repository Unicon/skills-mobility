import type { ExecutionSummary } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { useExecutionList } from "./useExecutionList";

vi.mock("@skills-mobility/contracts", () => ({
  orchestratorApi: {
    getExecution: vi.fn(),
    listExecutions: vi.fn(),
  },
}));

function summary(overrides: Partial<ExecutionSummary>): ExecutionSummary {
  return {
    execution_id: "exec_1",
    correlation_id: "corr_1",
    event_type: "skill_mastered",
    status: "completed",
    step_progress: { completed: 1, total: 1 },
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

describe("useExecutionList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  test("reconciles the list with each poll", async () => {
    const listExecutions = vi.mocked(orchestratorApi.listExecutions);
    listExecutions
      .mockResolvedValueOnce([summary({ execution_id: "exec_1" })])
      .mockResolvedValueOnce([summary({ execution_id: "exec_2" }), summary({ execution_id: "exec_1" })]);

    const { result } = renderHook(() => useExecutionList());

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.executions.map((e) => e.execution_id)).toEqual(["exec_1"]);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(result.current.executions.map((e) => e.execution_id)).toEqual(["exec_2", "exec_1"]);
  });

  test("polls continuously while mounted (no terminal stop)", async () => {
    const listExecutions = vi.mocked(orchestratorApi.listExecutions);
    listExecutions.mockResolvedValue([]);

    renderHook(() => useExecutionList());

    await act(async () => {
      await Promise.resolve();
    });
    expect(listExecutions).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(listExecutions).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(listExecutions).toHaveBeenCalledTimes(3);
  });

  test("passes correlationId through to the query", async () => {
    const listExecutions = vi.mocked(orchestratorApi.listExecutions);
    listExecutions.mockResolvedValue([]);

    renderHook(() => useExecutionList({ correlationId: "corr_abc" }));

    await act(async () => {
      await Promise.resolve();
    });
    expect(listExecutions).toHaveBeenCalledWith({ correlationId: "corr_abc" });
  });

  test("surfaces a fetch error", async () => {
    const listExecutions = vi.mocked(orchestratorApi.listExecutions);
    listExecutions.mockRejectedValueOnce(new Error("500 Internal Server Error"));

    const { result } = renderHook(() => useExecutionList());

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.error?.message).toBe("500 Internal Server Error");
  });
});
