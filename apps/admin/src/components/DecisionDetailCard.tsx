import type { DecisionArtifact, ExecutionMetadata } from "@skills-mobility/contracts";
import { ClampedBlock, ConfidenceMeter, highlightJson } from "@skills-mobility/ui";
import { useState } from "react";
import { KIND_LABEL } from "./decisionKinds";
import { buildMockInput, goalFor } from "./mockDecisionInput";

function buildResponseText(decision: DecisionArtifact): string {
  const pct = decision.confidence != null ? Math.round(decision.confidence * 100) : null;
  const choice = decision.outcome.replace(/_/g, " ");
  const confidenceClause = pct != null ? `, and am ${pct}% confident that this is the correct choice` : "";
  const rationale = decision.rationale
    ? decision.rationale.charAt(0).toLowerCase() + decision.rationale.slice(1)
    : "";
  const rationaleClause = rationale ? ` I came to this conclusion because ${rationale}` : "";
  const othersCount = decision.candidates.filter((c) => !c.selected).length;
  const weighedClause =
    othersCount > 0
      ? ` I weighed this against ${othersCount} other option${othersCount > 1 ? "s" : ""} before settling on this one.`
      : "";
  return `I went with ${choice}${confidenceClause}.${rationaleClause}${weighedClause}`;
}

export function DecisionDetailCard({
  decision,
  execution,
}: {
  decision: DecisionArtifact;
  execution: ExecutionMetadata;
}) {
  const [showRaw, setShowRaw] = useState(false);
  const candidates = [...decision.candidates].sort((a, b) => b.confidence - a.confidence);
  const hasRaw = Boolean(decision.artifact_ref || decision.invocation_log_ref);
  const mockInput = buildMockInput(decision, execution);

  return (
    <div className="decision-detail-card">
      <div className="decision-conversation-bubble">
        <header className="decision-conversation-header">Instructions</header>
        <ClampedBlock>
          <p className="decision-conversation-text">
            Your goal is to take this data and {goalFor(decision.kind)}. Here&rsquo;s the data:
          </p>
          <pre className="mono" dangerouslySetInnerHTML={{ __html: highlightJson(mockInput) }} />
        </ClampedBlock>
      </div>
      <div className="decision-conversation-bubble decision-conversation-bubble-response">
        <header className="decision-conversation-header">{KIND_LABEL[decision.kind]} Response</header>
        <ClampedBlock>
          <p className="decision-conversation-text">{buildResponseText(decision)}</p>
        </ClampedBlock>
      </div>
      {candidates.length > 0 ? (
        <ul className="decision-detail-candidates">
          {candidates.map((c) => (
            <li
              key={c.label}
              className={c.selected ? "decision-candidate-selected" : "decision-candidate-rejected"}
            >
              <span className="decision-candidate-label">{c.label}</span>
              <ConfidenceMeter value={c.confidence} />
              {c.rationale ? <span className="placeholder">{c.rationale}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
      {hasRaw ? (
        <>
          <button
            type="button"
            className="decision-detail-raw-toggle"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "Hide raw" : "View raw"}
          </button>
          {showRaw ? (
            <pre
              className="mono"
              dangerouslySetInnerHTML={{
                __html: highlightJson({
                  artifact_ref: decision.artifact_ref,
                  invocation_log_ref: decision.invocation_log_ref,
                }),
              }}
            />
          ) : null}
        </>
      ) : null}
    </div>
  );
}
