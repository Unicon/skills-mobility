import { useState } from "react";
import "./CopyableId.css";

export function CopyableId({
  value,
  display,
  label,
  onCopied,
}: {
  value: string;
  display: string;
  label: string;
  onCopied?: (label: string) => void;
}) {
  const [failed, setFailed] = useState(false);

  const handleClick = () => {
    const clipboard = navigator.clipboard;
    if (!clipboard) {
      setFailed(true);
      window.setTimeout(() => setFailed(false), 1600);
      return;
    }
    clipboard
      .writeText(value)
      .then(() => {
        setFailed(false);
        onCopied?.(label);
      })
      .catch(() => {
        setFailed(true);
        window.setTimeout(() => setFailed(false), 1600);
      });
  };

  return (
    <button
      type="button"
      className={failed ? "copyable-id copyable-id-failed" : "copyable-id"}
      title={failed ? "Copy failed" : `Copy ${label}`}
      aria-live="polite"
      onClick={handleClick}
    >
      {failed ? "Copy failed" : display}
    </button>
  );
}
