import * as Collapsible from "@radix-ui/react-collapsible";
import type { StepResult } from "@skills-mobility/contracts";
import { BotIcon } from "@skills-mobility/ui";
import { useState } from "react";
import { isAiBackedAction } from "./actionKinds";
import { PHASE_LABEL, stepPhase, type Phase } from "./stepPhases";

export function StepRow({
  step,
  activePhase,
  onActiveChange,
  selectedPhase = null,
}: {
  step: StepResult;
  activePhase: Phase | null;
  onActiveChange: (phase: Phase | null) => void;
  selectedPhase?: Phase | null;
}) {
  const [open, setOpen] = useState(false);
  const phase = stepPhase(step.action_id);
  const highlighted = phase != null && phase === activePhase;
  const selected = phase != null && phase === selectedPhase;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <button
          type="button"
          className={`step-row${selected ? " selected" : ""}${highlighted ? " highlighted" : ""}`}
          onMouseEnter={() => onActiveChange(phase)}
          onMouseLeave={() => onActiveChange(null)}
          onFocus={() => onActiveChange(phase)}
          onBlur={() => onActiveChange(null)}
        >
          <span>{step.action_id}</span>
          {isAiBackedAction(step.action_id) && (
            <span className="step-ai-badge" role="img" aria-label="AI-generated step" title="AI-generated step">
              <BotIcon size={14} />
            </span>
          )}
          {phase != null && <span className="step-phase-tag">{PHASE_LABEL[phase]}</span>}
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
