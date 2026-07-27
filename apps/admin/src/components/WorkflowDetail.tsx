import { CopyableId } from "@skills-mobility/ui";
import { useEffect, useState } from "react";
import { useExecution } from "../hooks/useExecution";
import { DecisionFlow } from "./DecisionFlow";
import type { Phase } from "./stepPhases";
import { StepRow } from "./StepRow";

export function WorkflowDetail({ executionId, onBack }: { executionId: string; onBack: () => void }) {
  const { execution, error } = useExecution(executionId);
  const [activePhase, setActivePhase] = useState<Phase | null>(null);

  useEffect(() => {
    if (error || !execution) setActivePhase(null);
  }, [error, execution]);

  return (
    <div>
      <button type="button" className="back-link" onClick={onBack}>
        ← Back to list
      </button>

      {error ? (
        <div className="empty">Unable to reach the Orchestrator read API.</div>
      ) : !execution ? (
        <div className="empty">Loading…</div>
      ) : (
        <>
          <div className="detail-header">
            <h2>
              {execution.event_type ?? "Workflow"}{" "}
              <span className={`status-chip ${execution.status}`}>{execution.status}</span>
            </h2>
            <div className="row">
              <CopyableId value={execution.execution_id} display={execution.execution_id} label="execution id" />
              <CopyableId
                value={execution.correlation_id}
                display={execution.correlation_id}
                label="correlation id"
              />
              <span className="mono">{execution.plan_id ?? "no plan"}</span>
            </div>
          </div>

          <div className="card">
            <header>Decision flow</header>
            <div className="body">
              <DecisionFlow
                execution={execution}
                activePhase={activePhase}
                onActivePhaseChange={setActivePhase}
              />
            </div>
          </div>

          <div className="card">
            <header>Step timeline</header>
            {execution.steps.length === 0 ? (
              <div className="body">
                <span className="placeholder">No steps recorded yet.</span>
              </div>
            ) : (
              execution.steps.map((step) => (
                <StepRow
                  key={step.step_id}
                  step={step}
                  activePhase={activePhase}
                  onActiveChange={setActivePhase}
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
