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

export interface Outcome {
  id: string;
  title: string;
  display_name: string;
  description: string;
  code: string;
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

// Orchestrator execution read model (Admin UI half). Hand-maintained mirror of
// services/orchestrator/src/orchestrator/schemas.py — that file is the source of
// truth; when its execution read-model schemas change, update these to match.

export type WorkflowStatus = "created" | "planning" | "ready" | "running" | "completed" | "failed";

export interface StepProgress {
  completed: number;
  total: number;
}

export interface ExecutionSummary {
  execution_id: string;
  correlation_id: string;
  event_type: string | null;
  status: WorkflowStatus;
  step_progress: StepProgress;
  created_at: string;
  updated_at: string;
}

export interface StepResult {
  step_id: number;
  action_id: string;
  status: "succeeded" | "skipped" | "failed";
  attempt: number;
  output: Record<string, unknown>;
  error: Record<string, unknown> | null;
  started_at: string;
  finished_at: string;
}

export type DecisionKind = "gate" | "delivery_targets" | "field_mapping" | "workflow_actions_plan";

export interface DecisionCandidate {
  label: string;
  confidence: number;
  rationale: string;
  selected: boolean;
}

/** Provenance of a decision (ADR-0022): real LLM seam output vs deterministic fallback. */
export type DecisionSource = "llm" | "deterministic_fallback";

export interface DecisionArtifact {
  kind: DecisionKind;
  confidence: number | null;
  rationale: string;
  outcome: string;
  candidates: DecisionCandidate[];
  artifact_ref: string | null;
  invocation_log_ref: string | null;
  decision_source: DecisionSource | null;
  created_at: string;
}

export interface ExecutionMetadata {
  execution_id: string;
  correlation_id: string;
  event_type: string | null;
  status: WorkflowStatus;
  decisions: DecisionArtifact[];
  plan_id: string | null;
  steps: StepResult[];
  result: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
