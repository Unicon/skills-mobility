import type { DecisionKind, ExecutionMetadata } from "@skills-mobility/contracts";
import { DecisionNode, FlowConnector, PipelineInfoNode } from "@skills-mobility/ui";
import { Fragment, useState } from "react";
import { KIND_LABEL, KIND_ORDER } from "./decisionKinds";
import { DecisionDetailCard } from "./DecisionDetailCard";
import { EventDetailCard } from "./EventDetailCard";
import { WalletDetailCard } from "./WalletDetailCard";

function EventIcon() {
  return (
    <svg width="29" height="27" viewBox="0 0 29.3339 27.3333" fill="none" aria-hidden="true">
      <path
        d="M1.3336 17.3333L4.66694 1.33333H24.6669L28.0003 17.3333"
        stroke="currentColor"
        strokeWidth="2.66667"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M1.3336 17.3333H8.60694L9.81827 21.3333H19.5156L20.7276 17.3333H28.0003V26H1.3336V17.3333Z"
        stroke="currentColor"
        strokeWidth="2.66667"
        strokeLinejoin="round"
      />
      <path
        d="M11.3336 10.1427L14.0003 13.3333L19.3336 8"
        stroke="currentColor"
        strokeWidth="2.66667"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function WalletIcon() {
  return (
    <svg width="32" height="26" viewBox="0 0 32.5 26" fill="none" aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M4.875 0C3.58207 0 2.34209 0.513615 1.42785 1.42785C0.513615 2.34209 0 3.58207 0 4.875V21.125C0 22.4179 0.513615 23.6579 1.42785 24.5721C2.34209 25.4864 3.58207 26 4.875 26H27.625C28.9179 26 30.1579 25.4864 31.0721 24.5721C31.9864 23.6579 32.5 22.4179 32.5 21.125V4.875C32.5 3.58207 31.9864 2.34209 31.0721 1.42785C30.1579 0.513615 28.9179 0 27.625 0H4.875ZM29.25 6.77625V4.875C29.25 4.44402 29.0788 4.0307 28.774 3.72595C28.4693 3.42121 28.056 3.25 27.625 3.25H4.875C4.44402 3.25 4.0307 3.42121 3.72595 3.72595C3.42121 4.0307 3.25 4.44402 3.25 4.875V6.77625C3.75862 6.5975 4.30625 6.5 4.875 6.5H27.625C28.1937 6.5 28.7414 6.5975 29.25 6.77625ZM3.25 11.375V13H11.375C11.4205 13 11.466 13.0022 11.5115 13.0065C11.8705 12.9751 12.2297 13.0639 12.5326 13.2589C12.8356 13.4539 13.0652 13.7441 13.1853 14.0839C13.4098 14.7172 13.825 15.2654 14.3738 15.6532C14.9226 16.0409 15.578 16.2491 16.25 16.2491C16.922 16.2491 17.5774 16.0409 18.1262 15.6532C18.675 15.2654 19.0902 14.7172 19.3147 14.0839C19.4348 13.7441 19.6644 13.4539 19.9674 13.2589C20.2703 13.0639 20.6295 12.9751 20.9885 13.0065C21.0329 13.0011 21.0784 12.9989 21.125 13H29.25V11.375C29.25 10.944 29.0788 10.5307 28.774 10.226C28.4693 9.92121 28.056 9.75 27.625 9.75H4.875C4.44402 9.75 4.0307 9.92121 3.72595 10.226C3.42121 10.5307 3.25 10.944 3.25 11.375ZM21.8806 16.25C21.31 17.2383 20.4892 18.059 19.5008 18.6295C18.5124 19.2 17.3912 19.5003 16.25 19.5C15.1088 19.5003 13.9876 19.2 12.9992 18.6295C12.0108 18.059 11.19 17.2383 10.6194 16.25H3.25V21.125C3.25 21.556 3.42121 21.9693 3.72595 22.274C4.0307 22.5788 4.44402 22.75 4.875 22.75H27.625C28.056 22.75 28.4693 22.5788 28.774 22.274C29.0788 21.9693 29.25 21.556 29.25 21.125V16.25H21.8806Z"
        fill="currentColor"
      />
    </svg>
  );
}

type ExpandedKey = DecisionKind | "event" | "wallet" | null;

export function DecisionFlow({ execution }: { execution: ExecutionMetadata }) {
  const [expandedKey, setExpandedKey] = useState<ExpandedKey>(null);
  const byKind = new Map(execution.decisions.map((d) => [d.kind, d]));
  const walletDelivered = execution.steps.some(
    (s) => s.action_id === "deliver_to_learncard_wallet" && s.status === "succeeded",
  );

  const toggle = (key: ExpandedKey) => setExpandedKey(expandedKey === key ? null : key);

  return (
    <div className="decision-flow">
      <div className="decision-flow-row">
        <PipelineInfoNode
          icon={<EventIcon />}
          label="Event"
          state="populated"
          expanded={expandedKey === "event"}
          onClick={() => toggle("event")}
        />
        <FlowConnector state="populated" />
        {execution.decisions.length === 0 ? (
          <DecisionNode
            label={KIND_LABEL.gate}
            confidence={null}
            state="pending"
            expanded={false}
            onClick={() => {}}
          />
        ) : (
          KIND_ORDER.map((kind, i) => {
            const isPopulated = byKind.has(kind);
            return (
              <Fragment key={kind}>
                {i > 0 && (
                  <FlowConnector state={byKind.has(KIND_ORDER[i - 1]) ? "populated" : "pending"} />
                )}
                <DecisionNode
                  label={KIND_LABEL[kind]}
                  confidence={byKind.get(kind)?.confidence ?? null}
                  state={isPopulated ? "populated" : "pending"}
                  expanded={isPopulated && expandedKey === kind}
                  onClick={isPopulated ? () => toggle(kind) : () => {}}
                />
              </Fragment>
            );
          })
        )}
        <FlowConnector state={walletDelivered ? "populated" : "pending"} />
        <PipelineInfoNode
          icon={<WalletIcon />}
          label="Wallet"
          state={walletDelivered ? "populated" : "pending"}
          expanded={walletDelivered && expandedKey === "wallet"}
          onClick={walletDelivered ? () => toggle("wallet") : () => {}}
        />
      </div>
      {expandedKey === "event" ? <EventDetailCard execution={execution} /> : null}
      {expandedKey === "wallet" && walletDelivered ? <WalletDetailCard execution={execution} /> : null}
      {expandedKey !== "event" && expandedKey !== "wallet" && expandedKey && byKind.get(expandedKey) ? (
        <DecisionDetailCard decision={byKind.get(expandedKey)!} execution={execution} />
      ) : null}
    </div>
  );
}
