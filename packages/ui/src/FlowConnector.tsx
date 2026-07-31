import { motion, useReducedMotion } from "motion/react";
import "./FlowConnector.css";

export function FlowConnector({ state }: { state: "populated" | "pending" }) {
  // DUPE:reduced-motion-guard
  const prefersReducedMotion = useReducedMotion();

  if (state === "pending") {
    return (
      <svg
        className="flow-connector flow-connector-pending"
        viewBox="0 0 40 2"
        preserveAspectRatio="none"
      >
        <line x1="0" y1="1" x2="40" y2="1" />
      </svg>
    );
  }

  return (
    <svg
      className="flow-connector flow-connector-populated"
      viewBox="0 0 40 2"
      preserveAspectRatio="none"
    >
      <motion.line
        x1="0"
        y1="1"
        x2="40"
        y2="1"
        initial={prefersReducedMotion ? false : { pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={prefersReducedMotion ? { duration: 0 } : { duration: 0.5, ease: "easeOut" }}
      />
    </svg>
  );
}
