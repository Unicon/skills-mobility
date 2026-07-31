import type { EventEnvelope } from "@skills-mobility/contracts";
import * as Dialog from "@radix-ui/react-dialog";
import { motion, useReducedMotion } from "motion/react";
import { useState } from "react";
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
  // DUPE:reduced-motion-guard
  const prefersReducedMotion = useReducedMotion();
  // Captured synchronously on first render (before Radix's own mount-autofocus
  // effect moves focus into the dialog), since there's no Dialog.Trigger here —
  // EnvelopeModal is mounted/unmounted by the caller rather than opened via a
  // colocated trigger, so Radix's default triggerRef-based restore is a no-op.
  const [openerElement] = useState(() => document.activeElement as HTMLElement | null);

  return (
    <Dialog.Root open onOpenChange={(next) => !next && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="scrim" />
        <Dialog.Content
          className="modal-anchor"
          aria-describedby={undefined}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            openerElement?.focus();
          }}
        >
          <motion.div
            className="modal"
            initial={prefersReducedMotion ? false : { opacity: 0, scale: 0.97, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={prefersReducedMotion ? { duration: 0 } : { type: "spring", stiffness: 400, damping: 32 }}
          >
            <header>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="envelope-dot" style={{ background: "var(--gold)" }} />
                <Dialog.Title asChild>
                  <span className="mono" style={{ fontWeight: 700, color: "var(--gold)" }}>
                    {envelope.metadata.event_name}
                  </span>
                </Dialog.Title>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="iconbtn"
                  title="Copy envelope JSON"
                  aria-label="Copy envelope JSON"
                  onClick={() => onCopy(JSON.stringify(envelope, null, 2), "envelope")}
                >
                  ⧉
                </button>
                <Dialog.Close asChild>
                  <button type="button" className="iconbtn" title="Close" aria-label="Close">
                    ✕
                  </button>
                </Dialog.Close>
              </div>
            </header>
            <pre dangerouslySetInnerHTML={{ __html: highlightJson(envelope) }} />
          </motion.div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
