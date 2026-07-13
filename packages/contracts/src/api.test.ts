import { afterEach, describe, expect, test, vi } from "vitest";
import { api } from "./index";
import type { CourseWithActions, RunResult } from "./types";

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
