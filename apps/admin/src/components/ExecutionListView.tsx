import type { ExecutionSummary } from "@skills-mobility/contracts";
import { CopyableId, eventColor } from "@skills-mobility/ui";
import { type FormEvent, useEffect, useState } from "react";
import { useExecutionList } from "../hooks/useExecutionList";

export function ExecutionListView({ onSelect }: { onSelect: (executionId: string) => void }) {
  const [pivotInput, setPivotInput] = useState("");
  const [correlationId, setCorrelationId] = useState<string | undefined>(undefined);
  const { executions, error } = useExecutionList({ correlationId });

  useEffect(() => {
    if (correlationId && executions.length === 1) {
      onSelect(executions[0].execution_id);
    }
  }, [correlationId, executions, onSelect]);

  const onSubmitPivot = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setCorrelationId(pivotInput.trim() || undefined);
  };

  const onClearPivot = () => {
    setCorrelationId(undefined);
    setPivotInput("");
  };

  return (
    <div>
      <form className="pivot" onSubmit={onSubmitPivot}>
        <input
          type="text"
          aria-label="Correlation id"
          placeholder="Paste a correlation_id to pivot…"
          value={pivotInput}
          onChange={(e) => setPivotInput(e.target.value)}
        />
        <button type="submit">Find</button>
        {correlationId && (
          <button type="button" onClick={onClearPivot}>
            Clear
          </button>
        )}
      </form>

      {error ? (
        <div className="empty">Unable to reach the Orchestrator read API.</div>
      ) : correlationId && executions.length === 0 ? (
        <div className="empty">No executions match correlation id “{correlationId}”.</div>
      ) : executions.length === 0 ? (
        <div className="empty">No executions yet.</div>
      ) : (
        <table className="exec-table">
          <thead>
            <tr>
              <th>Correlation</th>
              <th>Event</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            {executions.map((execution) => (
              <ExecutionRow key={execution.execution_id} execution={execution} onSelect={onSelect} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ExecutionRow({
  execution,
  onSelect,
}: {
  execution: ExecutionSummary;
  onSelect: (executionId: string) => void;
}) {
  const select = () => onSelect(execution.execution_id);

  return (
    <tr className={execution.status === "failed" ? "exec-row failed" : "exec-row"} onClick={select}>
      <td onClick={(e) => e.stopPropagation()}>
        <CopyableId value={execution.correlation_id} display={execution.correlation_id} label="correlation id" />
      </td>
      <td style={{ color: execution.event_type ? eventColor(execution.event_type) : undefined }}>
        <button type="button" className="row-open" aria-label={`Open workflow ${execution.execution_id}`} onClick={select}>
          {execution.event_type ?? "—"}
        </button>
      </td>
      <td>
        <span className={`status-chip ${execution.status}`}>{execution.status}</span>
      </td>
      <td>
        {execution.step_progress.completed}/{execution.step_progress.total}
      </td>
      <td className="mono">{execution.updated_at}</td>
    </tr>
  );
}
