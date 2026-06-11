import { motion } from "framer-motion";
import type { Scenario } from "../types";
import { eventColor } from "../util";

const SCENARIO_TYPE: Record<string, string> = {
  "skill-mastered": "skill_mastered",
  "course-completed": "course_completed",
  "badge-awarded": "badge_awarded",
};

export function ScenarioRail({
  scenarios,
  activeId,
  busyId,
  onSelect,
  onRun,
  onReset,
}: {
  scenarios: Scenario[];
  activeId: string | null;
  busyId: string | null;
  onSelect: (id: string) => void;
  onRun: (id: string) => void;
  onReset: (id: string) => void;
}) {
  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Scenarios</span>
        <span className="tag">{scenarios.length}</span>
      </div>
      <div className="col-body">
        {scenarios.map((s, i) => {
          const color = eventColor(SCENARIO_TYPE[s.id] ?? "");
          const active = activeId === s.id;
          const busy = busyId === s.id;
          return (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className={`scenario ${active ? "active" : ""}`}
              onClick={() => onSelect(s.id)}
            >
              <h4>
                <span className="dot" style={{ background: color }} />
                {s.title}
              </h4>
              <p>{s.description}</p>
              <div className="meta">
                <span className="tag">{s.event_count} event{s.event_count === 1 ? "" : "s"}</span>
                <span className="tag mono">{s.id}</span>
              </div>
              <div className="btn-row">
                <button
                  className="btn primary"
                  disabled={busy}
                  onClick={(e) => {
                    e.stopPropagation();
                    onRun(s.id);
                  }}
                >
                  {busy ? "Emitting…" : "▸ Emit"}
                </button>
                <button
                  className="btn ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onReset(s.id);
                  }}
                >
                  Reset
                </button>
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}
