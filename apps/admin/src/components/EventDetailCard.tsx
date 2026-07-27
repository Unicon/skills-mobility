import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { highlightJson } from "@skills-mobility/ui";
import { reconstructEventEnvelope } from "./mockDecisionInput";

export function EventDetailCard({ execution }: { execution: ExecutionMetadata }) {
  const envelope = reconstructEventEnvelope(execution);

  return (
    <div className="decision-detail-card">
      <p className="placeholder">
        Reconstructed from execution fields for display — the raw event body isn't
        persisted by the Orchestrator today.
      </p>
      <pre className="mono" dangerouslySetInnerHTML={{ __html: highlightJson(envelope) }} />
    </div>
  );
}
