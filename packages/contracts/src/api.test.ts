import { afterEach, describe, expect, test, vi } from "vitest";
import { api, orchestratorApi } from "./index";
import type { CourseWithActions, ExecutionMetadata, ExecutionSummary, RunResult } from "./types";

describe("api", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("courses() fetches from /demo/courses", async () => {
    const fixture: CourseWithActions[] = [
      {
        id: "course_1",
        name: "Intro to Testing",
        course_code: "TEST-101",
        kind: "standard",
        institution: "Acme U",
        term: "Fall 2026",
        workflow_state: "available",
        learners: [],
        actions: [],
      },
    ];
    const fetchSpy = vi.fn(async (path: string | URL | Request) => {
      expect(path).toBe("/demo/courses");
      return new Response(JSON.stringify(fixture), { status: 200 });
    });
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    await expect(api.courses()).resolves.toEqual(fixture);
  });

  test("runAction() POSTs scope + user_id in the body", async () => {
    const fixture: RunResult = {
      correlation_id: "corr_1",
      action_id: "action_1",
      scope: "one",
      emitted: [],
    };
    const fetchSpy = vi.fn(async (path: string | URL | Request, init?: RequestInit) => {
      expect(path).toBe("/demo/courses/course_1/actions");
      expect(JSON.parse(init?.body as string)).toEqual({
        action_id: "action_1",
        scope: "one",
        user_id: "learner_1",
      });
      return new Response(JSON.stringify(fixture), { status: 200 });
    });
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    await expect(api.runAction("course_1", "action_1", "one", "learner_1")).resolves.toEqual(
      fixture,
    );
  });

  test("throws with status and body detail on a non-ok response", async () => {
    globalThis.fetch = vi.fn(
      async () => new Response("course not found", { status: 404, statusText: "Not Found" }),
    ) as unknown as typeof fetch;

    await expect(api.courses()).rejects.toThrow("404 course not found");
  });
});

describe("orchestratorApi", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test("listExecutions() fetches /executions with no params by default", async () => {
    const fixture: ExecutionSummary[] = [
      {
        execution_id: "exec_1",
        correlation_id: "corr_1",
        event_type: "skill_mastered",
        status: "completed",
        step_progress: { completed: 2, total: 2 },
        created_at: "2026-07-09T00:00:00Z",
        updated_at: "2026-07-09T00:00:01Z",
      },
    ];
    const fetchSpy = vi.fn(async (path: string | URL | Request) => {
      expect(path).toBe("/executions");
      return new Response(JSON.stringify(fixture), { status: 200 });
    });
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    await expect(orchestratorApi.listExecutions()).resolves.toEqual(fixture);
  });

  test("listExecutions() encodes limit + correlationId as query params (correlation-pivot)", async () => {
    const fixture: ExecutionSummary[] = [];
    const fetchSpy = vi.fn(async (path: string | URL | Request) => {
      expect(path).toBe("/executions?limit=10&correlation_id=corr_1");
      return new Response(JSON.stringify(fixture), { status: 200 });
    });
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    await expect(
      orchestratorApi.listExecutions({ limit: 10, correlationId: "corr_1" }),
    ).resolves.toEqual(fixture);
  });

  test("getExecution() fetches /executions/{id}", async () => {
    const fixture: ExecutionMetadata = {
      execution_id: "exec_1",
      correlation_id: "corr_1",
      event_type: "skill_mastered",
      status: "completed",
      gate_decision: { decision: "continue_to_delivery_targets", confidence: 1, rationale: "stub" },
      plan_id: "phase1-skill-mastered.v1",
      steps: [],
      result: {},
      created_at: "2026-07-09T00:00:00Z",
      updated_at: "2026-07-09T00:00:01Z",
    };
    const fetchSpy = vi.fn(async (path: string | URL | Request) => {
      expect(path).toBe("/executions/exec_1");
      return new Response(JSON.stringify(fixture), { status: 200 });
    });
    globalThis.fetch = fetchSpy as unknown as typeof fetch;

    await expect(orchestratorApi.getExecution("exec_1")).resolves.toEqual(fixture);
  });

  test("getExecution() throws with status and body detail on not-found", async () => {
    globalThis.fetch = vi.fn(
      async () =>
        new Response('{"errors":[{"message":"execution exec_9 not found"}]}', {
          status: 404,
          statusText: "Not Found",
        }),
    ) as unknown as typeof fetch;

    await expect(orchestratorApi.getExecution("exec_9")).rejects.toThrow(
      /404 .*execution exec_9 not found/,
    );
  });
});
