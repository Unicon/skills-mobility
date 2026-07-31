import { useState } from "react";
import { api } from "@skills-mobility/contracts";

type State = "idle" | "busy" | "done" | "partial" | "failed";

/** Demo reset: one POST to the Mock LMS cascades the whole chain (Mock LMS →
 * Event Consumer dedup → Orchestrator executions), so a learner's events can
 * be re-run. Reports a partial reset honestly instead of pretending success. */
export function ResetDemoButton() {
  const [state, setState] = useState<State>("idle");

  const run = async () => {
    if (!window.confirm("Reset demo data? Clears all executions and re-run locks.")) return;
    setState("busy");
    try {
      const result = await api.reset();
      setState(result.event_consumer === "reset" ? "done" : "partial");
      window.setTimeout(() => window.location.assign("#/"), 600);
      window.setTimeout(() => window.location.reload(), 700);
    } catch {
      setState("failed");
    }
  };

  const label =
    state === "busy"
      ? "Resetting…"
      : state === "done"
        ? "Reset ✓"
        : state === "partial"
          ? "Partial reset — see logs"
          : state === "failed"
            ? "Reset failed"
            : "Reset demo";

  return (
    <button
      type="button"
      className="reset-demo"
      onClick={run}
      disabled={state === "busy"}
      title="Clears executions and ingress dedup across the chain so learner events can re-run"
    >
      {label}
    </button>
  );
}
