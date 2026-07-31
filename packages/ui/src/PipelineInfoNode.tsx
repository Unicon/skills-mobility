import type { ReactNode } from "react";
// Shares DecisionNode's card chrome (border/radius/padding/color-states) intentionally —
// this is the same pipeline-node shape without a confidence readout.
import "./DecisionNode.css";

export function PipelineInfoNode({
  icon,
  label,
  state,
  expanded,
  onClick,
  highlighted,
  onActiveChange,
}: {
  icon: ReactNode;
  label: string;
  state: "populated" | "pending";
  expanded: boolean;
  onClick: () => void;
  highlighted?: boolean;
  onActiveChange?: (active: boolean) => void;
}) {
  return (
    <button
      type="button"
      className={`decision-node pipeline-info-node decision-node-${state}${
        expanded ? " decision-node-expanded" : ""
      }${highlighted ? " decision-node-highlighted" : ""}`}
      onClick={onClick}
      onMouseEnter={() => onActiveChange?.(true)}
      onMouseLeave={() => onActiveChange?.(false)}
      onFocus={() => onActiveChange?.(true)}
      onBlur={() => onActiveChange?.(false)}
      aria-expanded={expanded}
      aria-label={label}
    >
      <span className="decision-node-badge">{icon}</span>
      <span className="decision-node-label">{label}</span>
    </button>
  );
}
