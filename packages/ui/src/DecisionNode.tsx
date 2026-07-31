import "./DecisionNode.css";
import { BotIcon } from "./BotIcon";

export function DecisionNode({
  label,
  confidence,
  state,
  expanded,
  onClick,
  highlighted,
  onActiveChange,
}: {
  label: string;
  confidence: number | null;
  state: "populated" | "pending";
  expanded: boolean;
  onClick: () => void;
  highlighted?: boolean;
  onActiveChange?: (active: boolean) => void;
}) {
  const confidenceText =
    state === "populated" && confidence != null
      ? `${Math.round(Math.max(0, Math.min(1, confidence)) * 100)}%`
      : "—";

  return (
    <button
      type="button"
      className={`decision-node decision-node-${state}${expanded ? " decision-node-expanded" : ""}${
        highlighted ? " decision-node-highlighted" : ""
      }`}
      onClick={onClick}
      onMouseEnter={() => onActiveChange?.(true)}
      onMouseLeave={() => onActiveChange?.(false)}
      onFocus={() => onActiveChange?.(true)}
      onBlur={() => onActiveChange?.(false)}
      aria-expanded={expanded}
      aria-label={label}
    >
      <span className="decision-node-top">
        <span className="decision-node-badge">
          <BotIcon />
        </span>
        <span className="decision-node-confidence">{confidenceText}</span>
      </span>
      <span className="decision-node-label">{label}</span>
    </button>
  );
}
