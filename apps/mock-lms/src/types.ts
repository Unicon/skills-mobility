// Mirrors the mock-lms service responses (services/mock-lms).

export type Role = "instructor" | "admin";

export interface EventSpec {
  event_type: string;
  user_id: string;
  course_id: string;
  outcome_id: string | null;
  assignment_id: string | null;
  badge_id?: string | null;
  badge_name?: string | null;
  credential_type?: string | null;
}

export interface Scenario {
  id: string;
  title: string;
  description: string;
  event_count: number;
  events: EventSpec[];
}

export interface Course {
  id: string;
  name: string;
  course_code: string;
  workflow_state: string;
}

export interface Outcome {
  id: string;
  title: string;
  display_name: string;
  description: string;
  mastery_points: number;
  points_possible: number;
}

export interface Assignment {
  id: string;
  course_id: string;
  name: string;
  description: string;
  points_possible: number;
  due_at: string | null;
}

export interface Submission {
  id: string;
  course_id: string;
  assignment_id: string;
  user_id: string;
  score: number | null;
  grade: string | null;
  workflow_state: string;
  submitted_at: string | null;
  graded_at: string | null;
}

export interface OutcomeResult {
  id: string;
  user_id: string;
  outcome_id: string;
  assignment_id: string | null;
  score: number;
  possible: number;
  mastery: boolean;
  submitted_or_assessed_at: string | null;
}

export interface EventEnvelope {
  metadata: {
    event_name: string;
    event_time: string;
    producer: string;
    user_id: string | null;
    context_type: string | null;
    context_id: string | null;
    event_id: string;
    correlation_id: string;
    scenario_id: string | null;
    [k: string]: unknown;
  };
  body: Record<string, unknown>;
}

export interface Emission {
  seq: number;
  emission_id: string;
  correlation_id: string;
  scenario_id: string | null;
  event_type: string;
  event_name: string;
  event_time: string;
  target: string;
  envelope: EventEnvelope;
}
