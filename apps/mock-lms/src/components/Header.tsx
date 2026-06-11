import type { Role } from "../types";
import type { StreamState } from "../hooks/useEmissionStream";

const LABEL: Record<StreamState, string> = {
  connecting: "CONNECTING",
  live: "LIVE",
  down: "OFFLINE",
};

export function Header({
  state,
  count,
  role,
  onRole,
}: {
  state: StreamState;
  count: number;
  role: Role;
  onRole: (r: Role) => void;
}) {
  return (
    <header className="topbar">
      <div className="wordmark">
        <b>
          MOCK<span>·</span>LMS
        </b>
        <small>Event Producer — Skills Mobility POC</small>
      </div>

      <div className="topbar-spacer" />

      <div className="statuschip" title="Server-Sent Events feed status">
        <span className={`dot ${state === "live" ? "live" : state === "down" ? "down" : ""}`} />
        {LABEL[state]}
        <span style={{ color: "var(--ink-faint)" }}>·</span>
        <span style={{ color: "var(--gold)" }}>{count}</span> emitted
      </div>

      <div className="role-toggle" title="CloudFront-layer role (ADR-0002)">
        {(["instructor", "admin"] as Role[]).map((r) => (
          <button key={r} className={role === r ? "on" : ""} onClick={() => onRole(r)}>
            {r}
          </button>
        ))}
      </div>
    </header>
  );
}
