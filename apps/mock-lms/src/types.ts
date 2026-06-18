// Mirrors the mock-lms service responses (services/mock-lms).

export type CourseKind = "standard" | "digital_credential";

export interface Learner {
  id: string;
  name: string;
  email: string;
}

export interface ActionView {
  id: string;
  label: string;
  assignment_id: string;
  assignment_name: string | null;
  event_type: string | null;
}

export interface Course {
  id: string;
  name: string;
  course_code: string;
  kind: CourseKind;
  institution: string;
  term: string;
  workflow_state: string;
}

export interface CourseWithActions extends Course {
  learners: Learner[];
  actions: ActionView[];
}

export interface ModuleItem {
  id: string;
  title: string;
  type: string;
  content_id: string | null;
}

export interface Module {
  id: string;
  name: string;
  position: number;
  items: ModuleItem[];
}

export interface Assignment {
  id: string;
  course_id: string;
  name: string;
  description: string;
  points_possible: number;
  due_at: string | null;
  role: string;
  module_id: string | null;
  outcome_id: string | null;
  badge_id: string | null;
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

export interface RubricCriterion {
  id: string;
  description: string;
  points: number;
}

export interface Rubric {
  id: string;
  title: string;
  assignment_id: string | null;
  criteria: RubricCriterion[];
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
    action_id: string | null;
    [k: string]: unknown;
  };
  body: Record<string, unknown>;
}

export type Scope = "one" | "all";

export interface RunResult {
  correlation_id: string;
  action_id: string;
  scope: Scope;
  emitted: EventEnvelope[];
}
