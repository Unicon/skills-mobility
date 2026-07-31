import * as Collapsible from "@radix-ui/react-collapsible";
import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { highlightJson } from "@skills-mobility/ui";
import { useState } from "react";
import certificateUrl from "../assets/certificate.svg";

function asObject(x: unknown): Record<string, unknown> | undefined {
  return typeof x === "object" && x !== null ? (x as Record<string, unknown>) : undefined;
}

function readString(obj: unknown, ...path: string[]): string | undefined {
  let current: unknown = obj;
  for (const key of path) {
    current = asObject(current)?.[key];
  }
  return typeof current === "string" ? current : undefined;
}

export function BadgeViewer({ execution }: { execution: ExecutionMetadata }) {
  const [open, setOpen] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  const step = execution.steps.find(
    (s) => s.action_id === "issue_learncard_badge" && s.status === "succeeded",
  );
  const credential = asObject(asObject(asObject(step?.output)?.result)?.issued_credential);
  if (!credential) return null;

  const achievementName = readString(credential, "credentialSubject", "achievement", "name");
  const achievementDescription = readString(
    credential,
    "credentialSubject",
    "achievement",
    "description",
  );
  const issuerId = readString(credential, "issuer", "id");
  const recipientId = readString(credential, "credentialSubject", "id");

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <Collapsible.Trigger asChild>
        <button type="button" className="badge-certificate">
          <span className="badge-certificate-art-wrap">
            <img src={certificateUrl} alt="" className="badge-certificate-art" />
            <span className="badge-certificate-title">{achievementName ?? "Achievement"}</span>
          </span>
          {recipientId ? <span className="badge-certificate-recipient mono">{recipientId}</span> : null}
        </button>
      </Collapsible.Trigger>
      <Collapsible.Content>
        <div className="decision-detail-card">
          <ul className="decision-detail-candidates">
            {achievementName ? (
              <li>
                <span className="decision-candidate-label">achievement</span>
                <span>{achievementName}</span>
              </li>
            ) : null}
            {achievementDescription ? (
              <li>
                <span className="decision-candidate-label">description</span>
                <span>{achievementDescription}</span>
              </li>
            ) : null}
            {issuerId ? (
              <li>
                <span className="decision-candidate-label">issuer</span>
                <span className="mono">{issuerId}</span>
              </li>
            ) : null}
            {recipientId ? (
              <li>
                <span className="decision-candidate-label">recipient</span>
                <span className="mono">{recipientId}</span>
              </li>
            ) : null}
          </ul>
          <button
            type="button"
            className="decision-detail-raw-toggle"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "Hide raw" : "View raw"}
          </button>
          {showRaw ? (
            <pre className="mono" dangerouslySetInnerHTML={{ __html: highlightJson(credential) }} />
          ) : null}
        </div>
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
