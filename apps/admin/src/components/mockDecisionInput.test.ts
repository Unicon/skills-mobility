import type { DecisionArtifact, ExecutionMetadata } from "@skills-mobility/contracts";
import { describe, expect, test } from "vitest";
import { buildMockInput, goalFor, reconstructEventEnvelope } from "./mockDecisionInput";

const execution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "course_completed",
  status: "completed",
  decisions: [],
  plan_id: "phase1-course_completed.v1",
  steps: [],
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

function decisionOf(kind: DecisionArtifact["kind"]): DecisionArtifact {
  return {
    kind,
    confidence: 0.9,
    rationale: "",
    outcome: "ok",
    candidates: [],
    artifact_ref: null,
    invocation_log_ref: null,
    decision_source: null,
    created_at: "",
  };
}

describe("reconstructEventEnvelope", () => {
  test("carries the execution's real event_type, correlation_id, and execution_id", () => {
    const envelope = reconstructEventEnvelope(execution);
    expect(envelope.metadata.event_name).toBe("course_completed");
    expect(envelope.metadata.correlation_id).toBe("corr_1");
    expect(envelope.metadata.event_id).toBe("exec_1");
  });
});

describe("goalFor", () => {
  test("returns a distinct, non-empty goal sentence for every decision kind", () => {
    const kinds: DecisionArtifact["kind"][] = [
      "gate",
      "delivery_targets",
      "field_mapping",
      "workflow_actions_plan",
    ];
    const goals = kinds.map(goalFor);
    expect(goals.every((g) => g.length > 0)).toBe(true);
    expect(new Set(goals).size).toBe(kinds.length);
  });
});

describe("buildMockInput", () => {
  test("gate input embeds the reconstructed event envelope", () => {
    const input = buildMockInput(decisionOf("gate"), execution) as { event: { metadata: { event_id: string } } };
    expect(input.event.metadata.event_id).toBe("exec_1");
  });

  test("delivery_targets input carries the fields the seeded mock rationale cites", () => {
    const input = buildMockInput(decisionOf("delivery_targets"), execution) as {
      learner_context: { wallet_status: string; resume_on_file: boolean };
    };
    expect(input.learner_context.wallet_status).toBe("active");
    expect(input.learner_context.resume_on_file).toBe(false);
  });

  test("field_mapping input carries source_payloads with a course name and completion date", () => {
    const input = buildMockInput(decisionOf("field_mapping"), execution) as {
      source_payloads: { course: { name: string }; completion_date: string };
    };
    expect(input.source_payloads.course.name).toBeTruthy();
    expect(input.source_payloads.completion_date).toBe("2026-07-09T00:00:01Z");
  });

  test("workflow_actions_plan input carries the selected targets and the event envelope", () => {
    const input = buildMockInput(decisionOf("workflow_actions_plan"), execution) as {
      selected_targets: string[];
      event: { metadata: { event_id: string } };
    };
    expect(input.selected_targets).toContain("learncard_wallet");
    expect(input.event.metadata.event_id).toBe("exec_1");
  });
});
