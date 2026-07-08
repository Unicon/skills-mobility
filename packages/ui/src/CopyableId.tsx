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
  onCopied?: (text: string, label: string) => void;
}) {
  const [failed, setFailed] = useState(false);

  const handleClick = () => {
    navigator.clipboard
      .writeText(value)
      .then(() => {
        setFailed(false);
        onCopied?.(value, label);
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
      onClick={handleClick}
    >
      {failed ? "Copy failed" : display}
    </button>
  );
}
