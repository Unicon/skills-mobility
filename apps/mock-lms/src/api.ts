import type {
  Assignment,
  Course,
  Emission,
  Outcome,
  OutcomeResult,
  Role,
  Scenario,
  Submission,
} from "./types";

// Role is conveyed via the CloudFront-layer header the service trusts (ADR-0002).
let currentRole: Role = "instructor";
export function setRole(role: Role) {
  currentRole = role;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "X-Demo-Role": currentRole, "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  scenarios: () => req<Scenario[]>("/demo/scenarios"),
  runScenario: (id: string) =>
    req<{ correlation_id: string; emissions: unknown[] }>(`/demo/scenarios/${id}/run`, {
      method: "POST",
    }),
  resetScenario: (id: string) =>
    req<{ ok: boolean }>(`/demo/scenarios/${id}/reset`, { method: "POST" }),
  emissions: (since = 0) =>
    req<{ cursor: number; emissions: Emission[] }>(`/demo/emissions?since=${since}`),

  course: (courseId: string) => req<Course>(`/api/v1/courses/${courseId}`),
  outcome: (outcomeId: string) => req<Outcome>(`/api/v1/outcomes/${outcomeId}`),
  assignments: (courseId: string) =>
    req<Assignment[]>(`/api/v1/courses/${courseId}/assignments`),
  submissions: (courseId: string, userId: string) =>
    req<Submission[]>(
      `/api/v1/courses/${courseId}/students/submissions?student_ids[]=${userId}`,
    ),
  outcomeResults: (courseId: string, userId: string, outcomeId: string) =>
    req<{ outcome_results: OutcomeResult[] }>(
      `/api/v1/courses/${courseId}/outcome_results?user_ids[]=${userId}&outcome_ids[]=${outcomeId}&include[]=alignments`,
    ),
};
