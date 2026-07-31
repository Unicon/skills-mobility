import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { PHASE_LABEL } from "./stepPhases";

// Mirrors stepPhases.ts's STEP_PHASE domain — deliver_to_smartresume isn't on
// main yet (PR #89, unmerged); listed here so a SmartResume-only delivery
// still names its target instead of falling back to a bare action_id.
const DELIVERY_TARGET_LABEL: Record<string, string> = {
  deliver_to_learncard_wallet: "LearnCard Wallet",
  deliver_to_smartresume: "SmartResume",
};

export function DeliveredDetailCard({ execution }: { execution: ExecutionMetadata }) {
  const recipient =
    typeof execution.result.recipient_profile_id === "string"
      ? execution.result.recipient_profile_id
      : "unknown";

  const deliveredTargets = execution.steps
    .filter((s) => s.status === "succeeded" && s.action_id in DELIVERY_TARGET_LABEL)
    .map((s) => DELIVERY_TARGET_LABEL[s.action_id]);

  return (
    <div className="decision-detail-card">
      <p className="placeholder">
        Mocked — there is no real {PHASE_LABEL.delivered}-confirmation callback today. Only
        the recipient below is real (from the execution's result).
      </p>
      <div className="decision-detail-top">
        <span className="status-chip received">received</span>
      </div>
      <ul className="decision-detail-candidates">
        <li>
          <span className="decision-candidate-label">delivered to</span>
          <span className="mono">{deliveredTargets.join(", ") || "unknown"}</span>
        </li>
        <li>
          <span className="decision-candidate-label">recipient</span>
          <span className="mono">{recipient}</span>
        </li>
        <li>
          <span className="decision-candidate-label">received_at</span>
          <span className="mono">{execution.updated_at}</span>
        </li>
      </ul>
    </div>
  );
}
