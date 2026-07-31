import type { DecisionArtifact, EventEnvelope, ExecutionMetadata } from "@skills-mobility/contracts";

/** Reconstructed for display — the raw event body isn't persisted by the
 * Orchestrator today. Shared by EventDetailCard and the decision-service mock
 * inputs below, since it's the same illustrative event in both places. */
export function reconstructEventEnvelope(execution: ExecutionMetadata): EventEnvelope {
  return {
    metadata: {
      event_name: execution.event_type ?? "unknown_event",
      event_time: execution.created_at,
      producer: "mock-lms",
      user_id: null,
      context_type: null,
      context_id: null,
      event_id: execution.execution_id,
      correlation_id: execution.correlation_id,
      action_id: null,
    },
    body: {},
  };
}

const KIND_GOAL: Record<DecisionArtifact["kind"], string> = {
  gate: "decide whether this workflow event should proceed to delivery-target selection, or terminate early with a named business outcome",
  delivery_targets: "select which downstream systems should receive this credential",
  field_mapping:
    "map the supplied source payloads to the target credential schema, emitting machine-executable JSONata",
  workflow_actions_plan:
    "generate the ordered plan of steps to deliver this credential to the selected targets",
};

export function goalFor(kind: DecisionArtifact["kind"]): string {
  return KIND_GOAL[kind];
}

/** None of the four LLM Decision Services persist their rendered prompt/input
 * anywhere today (see ADR-0010 gap). This reconstructs a plausible input per
 * kind, shaped after the real request contracts (SelectionRequest,
 * MappingRequest, GateRequest, PlanRequest) — grounded in real execution
 * fields where we have them, illustrative otherwise. */
export function buildMockInput(decision: DecisionArtifact, execution: ExecutionMetadata): unknown {
  switch (decision.kind) {
    case "gate":
      return {
        execution_id: execution.execution_id,
        event_id: execution.execution_id,
        event_type: execution.event_type,
        event: reconstructEventEnvelope(execution),
        context_bundle: { learner: { profile_id: "smi-demo-learner" }, course: {} },
      };
    case "delivery_targets":
      return {
        execution_id: execution.execution_id,
        event_id: execution.execution_id,
        event_type: execution.event_type,
        source_system: "mock_lms",
        learner_context: {
          wallet_status: "active",
          prior_deliveries: 3,
          resume_on_file: false,
        },
      };
    case "field_mapping":
      return {
        execution_id: execution.execution_id,
        event_id: execution.execution_id,
        transformation_type: "issuer_payload",
        source_system: "mock_lms",
        fetch_profile_id: "smi-demo-learner",
        delivery_target: "learncard_wallet",
        synthesis_allowed: true,
        source_payloads: {
          course: { name: "Intro to Data Ethics" },
          completion_date: execution.updated_at,
        },
      };
    case "workflow_actions_plan":
      return {
        execution_id: execution.execution_id,
        event_id: execution.execution_id,
        event_type: execution.event_type,
        source_system: "mock_lms",
        selected_targets: ["learncard_issuer", "learncard_wallet"],
        event: reconstructEventEnvelope(execution),
      };
  }
}
