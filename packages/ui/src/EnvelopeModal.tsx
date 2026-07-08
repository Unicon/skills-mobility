import type { EventEnvelope } from "@skills-mobility/contracts";
import { motion } from "motion/react";
import { highlightJson } from "./highlightJson";
import "./EnvelopeModal.css";

export function EnvelopeModal({
  envelope,
  onClose,
  onCopy,
}: {
  envelope: EventEnvelope;
  onClose: () => void;
  onCopy: (text: string, label: string) => void;
}) {
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
            <span className="envelope-dot" style={{ background: "var(--gold)" }} />
            <span className="mono" style={{ fontWeight: 700, color: "var(--gold)" }}>
              {envelope.metadata.event_name}
            </span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="iconbtn"
              title="Copy envelope JSON"
              onClick={() => onCopy(JSON.stringify(envelope, null, 2), "envelope")}
            >
              ⧉
            </button>
            <button className="iconbtn" title="Close" onClick={onClose}>
              ✕
            </button>
          </div>
        </header>
        <pre dangerouslySetInnerHTML={{ __html: highlightJson(envelope) }} />
      </motion.div>
    </div>
  );
}
