import { motion, useReducedMotion } from "motion/react";
import "./ConfidenceMeter.css";

export function ConfidenceMeter({ value, label }: { value: number; label?: string }) {
  // DUPE:reduced-motion-guard
  const prefersReducedMotion = useReducedMotion();
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const tier = value < 0.5 ? "low" : value <= 0.8 ? "mid" : "high";

  return (
    <div className="confidence-meter" data-tier={tier}>
      {label ? <span className="confidence-meter-label">{label}</span> : null}
      <div className="confidence-meter-track">
        <motion.div
          className="confidence-meter-fill"
          initial={prefersReducedMotion ? false : { width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={
            prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }
          }
        />
      </div>
      <span className="confidence-meter-value">{pct}%</span>
    </div>
  );
}
