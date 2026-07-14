import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { orchestratorApi } from "@skills-mobility/contracts";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { useExecution } from "./useExecution";

vi.mock("@skills-mobility/contracts", () => ({
  orchestratorApi: {
    getExecution: vi.fn(),
    listExecutions: vi.fn(),
  },
}));

const baseExecution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "running",
  gate_decision: null,
  plan_id: null,
  steps: [],
  result: {},
  created_at: "",
  updated_at: "",
};

describe("useExecution", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  test("stops polling once the execution reaches a terminal status", async () => {
    const getExecution = vi.mocked(orchestratorApi.getExecution);
    getExecution
      .mockResolvedValueOnce({ ...baseExecution, status: "running" })
      .mockResolvedValueOnce({ ...baseExecution, status: "completed" });

    const { result } = renderHook(() => useExecution("exec_1"));

    await act(async () => {
      await Promise.resolve();
    });
    expect(result.current.execution?.status).toBe("running");
    expect(getExecution).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(result.current.execution?.status).toBe("completed");
    expect(getExecution).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(getExecution).toHaveBeenCalledTimes(2);
  });

  test("keeps polling while the execution is non-terminal", async () => {
    const getExecution = vi.mocked(orchestratorApi.getExecution);
    getExecution.mockResolvedValue({ ...baseExecution, status: "running" });

    renderHook(() => useExecution("exec_1"));

    await act(async () => {
      await Promise.resolve();
    });
    expect(getExecution).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(getExecution).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(getExecution).toHaveBeenCalledTimes(3);
  });

  test("surfaces a fetch error", async () => {
    const getExecution = vi.mocked(orchestratorApi.getExecution);
    getExecution.mockRejectedValueOnce(new Error("404 execution exec_missing not found"));

    const { result } = renderHook(() => useExecution("exec_missing"));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.error?.message).toBe("404 execution exec_missing not found");
  });

  test("does not fetch when executionId is null", async () => {
    const getExecution = vi.mocked(orchestratorApi.getExecution);

    const { result } = renderHook(() => useExecution(null));

    await act(async () => {
      await Promise.resolve();
    });

    expect(getExecution).not.toHaveBeenCalled();
    expect(result.current.execution).toBeNull();
  });
});
