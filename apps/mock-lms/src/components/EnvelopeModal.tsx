import { motion } from "framer-motion";
import type { Emission } from "../types";
import { eventColor, highlightJson } from "../util";

export function EnvelopeModal({
  emission,
  onClose,
  onCopy,
}: {
  emission: Emission;
  onClose: () => void;
  onCopy: (text: string, label: string) => void;
}) {
  const color = eventColor(emission.event_type);
  return (
    <div className="scrim" onClick={onClose}>
      <motion.div
        className="modal"
        initial={{ opacity: 0, scale: 0.97, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 400, damping: 32 }}
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span className="dot" style={{ background: color }} />
            <span className="mono" style={{ fontWeight: 700, color }}>
              {emission.event_name}
            </span>
            <span className="tag">{emission.event_type}</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="iconbtn"
              title="Copy envelope JSON"
              onClick={() => onCopy(JSON.stringify(emission.envelope, null, 2), "envelope")}
            >
              ⧉
            </button>
            <button className="iconbtn" title="Close" onClick={onClose}>
              ✕
            </button>
          </div>
        </header>
        <pre dangerouslySetInnerHTML={{ __html: highlightJson(emission.envelope) }} />
      </motion.div>
    </div>
  );
}
