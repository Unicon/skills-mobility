import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import "./ClampedBlock.css";

export function ClampedBlock({
  children,
  maxHeight = 160,
}: {
  children: ReactNode;
  maxHeight?: number;
}) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);

  useEffect(() => {
    const el = contentRef.current;
    if (el) {
      setOverflowing(el.scrollHeight > maxHeight + 1);
    }
  }, [children, maxHeight]);

  return (
    <div className="clamped-block">
      <div
        ref={contentRef}
        className={`clamped-block-content${!expanded && overflowing ? " clamped-block-content-clamped" : ""}`}
        style={!expanded ? { maxHeight } : undefined}
      >
        {children}
      </div>
      {overflowing ? (
        <button type="button" className="clamped-block-toggle" onClick={() => setExpanded((v) => !v)}>
          {expanded ? "Show less" : "Show more"}
        </button>
      ) : null}
    </div>
  );
}
