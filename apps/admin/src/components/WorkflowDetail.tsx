import { CopyableId } from "@skills-mobility/ui";
import { useExecution } from "../hooks/useExecution";
import { StepRow } from "./StepRow";

export function WorkflowDetail({ executionId, onBack }: { executionId: string; onBack: () => void }) {
  const { execution, error } = useExecution(executionId);

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
            <header>Decision log</header>
            <div className="body">
              {execution.gate_decision ? (
                <pre className="mono">{JSON.stringify(execution.gate_decision, null, 2)}</pre>
              ) : (
                <span className="placeholder">No decision recorded yet.</span>
              )}
            </div>
          </div>

          <div className="card">
            <header>Step timeline</header>
            {execution.steps.length === 0 ? (
              <div className="body">
                <span className="placeholder">No steps recorded yet.</span>
              </div>
            ) : (
              execution.steps.map((step) => <StepRow key={step.step_id} step={step} />)
            )}
          </div>
        </>
      )}
    </div>
  );
}
