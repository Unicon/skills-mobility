import * as Collapsible from "@radix-ui/react-collapsible";
import type { StepResult } from "@skills-mobility/contracts";
import { useState } from "react";

export function StepRow({ step }: { step: StepResult }) {
  const [open, setOpen] = useState(false);

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <button type="button" className="step-row">
          <span>{step.action_id}</span>
          <span className={`status-chip ${step.status}`}>{step.status}</span>
        </button>
      </Collapsible.Trigger>
      <Collapsible.Content className="step-panel">
        <div className="row">
          <span>Attempt {step.attempt}</span>
          <span className="mono">
            {step.started_at} → {step.finished_at}
          </span>
        </div>
        <p className="placeholder">Resolved inputs not yet available (FR-AU-18a).</p>
        <pre>{JSON.stringify(step.output, null, 2)}</pre>
        {step.error && <pre className="mono">{JSON.stringify(step.error, null, 2)}</pre>}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
