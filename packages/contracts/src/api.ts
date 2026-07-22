import type {
  Assignment,
  Course,
  CourseWithActions,
  ExecutionMetadata,
  ExecutionSummary,
  Module,
  Outcome,
  Rubric,
  RunResult,
  Scope,
  Submission,
} from "./types";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Emission control (UI-facing).
  courses: () => req<CourseWithActions[]>("/demo/courses"),
  runAction: (courseId: string, action_id: string, scope: Scope, user_id?: string) =>
    req<RunResult>(`/demo/courses/${courseId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action_id, scope, user_id: user_id ?? null }),
    }),
  reset: () => req<{ ok: boolean }>("/demo/reset", { method: "POST" }),

  // LMS Resource APIs (the same reads the Context Builder uses).
  course: (courseId: string) => req<Course>(`/api/v1/courses/${courseId}`),
  modules: (courseId: string) =>
    req<Module[]>(`/api/v1/courses/${courseId}/modules?include[]=items`),
  assignments: (courseId: string) =>
    req<Assignment[]>(`/api/v1/courses/${courseId}/assignments`),
  rubrics: (courseId: string) => req<Rubric[]>(`/api/v1/courses/${courseId}/rubrics`),
  outcome: (outcomeId: string) =>
    req<Outcome>(`/api/v1/outcomes/${encodeURIComponent(outcomeId)}`),
  submissions: (courseId: string, userId: string) =>
    req<Submission[]>(
      `/api/v1/courses/${courseId}/students/submissions?student_ids[]=${encodeURIComponent(userId)}`,
    ),
};

// Orchestrator read client (Admin UI half).
export const orchestratorApi = {
  listExecutions: ({ limit, correlationId }: { limit?: number; correlationId?: string } = {}) => {
    const params = new URLSearchParams();
    if (limit !== undefined) params.set("limit", String(limit));
    if (correlationId) params.set("correlation_id", correlationId);
    const qs = params.toString();
    return req<ExecutionSummary[]>(`/executions${qs ? `?${qs}` : ""}`);
  },
  getExecution: (executionId: string) =>
    req<ExecutionMetadata>(`/executions/${encodeURIComponent(executionId)}`),
};
