import { AnimatePresence, motion } from "framer-motion";
import type { Emission } from "../types";
import { clockTime, eventColor, shortId } from "../util";

export function EmissionTimeline({
  emissions,
  onCopy,
  onOpen,
}: {
  emissions: Emission[];
  onCopy: (text: string, label: string) => void;
  onOpen: (e: Emission) => void;
}) {
  const newestSeq = emissions[0]?.seq;

  return (
    <section className="col">
      <div className="col-head">
        <span className="eyebrow">Emission Timeline — live</span>
        <span className="tag">{emissions.length}</span>
      </div>
      <div className="col-body">
        {emissions.length === 0 && (
          <div className="empty">
            <div className="big">⠿</div>
            Waiting for events.
            <br />
            Run a scenario to emit onto the bus.
          </div>
        )}
        <div className="timeline">
          <AnimatePresence initial={false}>
            {emissions.map((e) => {
              const color = eventColor(e.event_type);
              return (
                <motion.div
                  key={e.emission_id}
                  layout
                  initial={{ opacity: 0, x: 24, height: 0 }}
                  animate={{ opacity: 1, x: 0, height: "auto" }}
                  exit={{ opacity: 0 }}
                  transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  className={`emission ${e.seq === newestSeq ? "fresh" : ""}`}
                  style={{ ["--type-color" as string]: color }}
                  onClick={() => onOpen(e)}
                >
                  <div className="e-top">
                    <span className="e-name">{e.event_name}</span>
                    <span className="e-time">{clockTime(e.event_time)}</span>
                  </div>
                  <div className="e-meta">
                    {e.scenario_id && <span className="tag">{e.scenario_id}</span>}
                    <span
                      className="kv copyable"
                      title="Copy correlation id"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        onCopy(e.correlation_id, "correlation id");
                      }}
                    >
                      <b>corr</b> {shortId(e.correlation_id)}
                    </span>
                    <span className="kv">
                      <b>→</b> {e.target}
                    </span>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
