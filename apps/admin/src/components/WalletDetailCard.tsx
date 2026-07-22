import type { ExecutionMetadata } from "@skills-mobility/contracts";

export function WalletDetailCard({ execution }: { execution: ExecutionMetadata }) {
  const recipient =
    typeof execution.result.recipient_profile_id === "string"
      ? execution.result.recipient_profile_id
      : "unknown";

  return (
    <div className="decision-detail-card">
      <p className="placeholder">
        Mocked — there is no real wallet delivery-confirmation callback today. Only
        the recipient below is real (from the execution's result).
      </p>
      <div className="decision-detail-top">
        <span className="status-chip received">received</span>
      </div>
      <ul className="decision-detail-candidates">
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
