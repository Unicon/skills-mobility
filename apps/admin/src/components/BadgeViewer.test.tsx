import type { ExecutionMetadata, StepResult } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { BadgeViewer } from "./BadgeViewer";

const baseExecution: ExecutionMetadata = {
  execution_id: "exec_1",
  correlation_id: "corr_1",
  event_type: "skill_mastered",
  status: "completed",
  decisions: [],
  plan_id: "phase1-skill_mastered.v1",
  steps: [],
  result: {},
  created_at: "2026-07-09T00:00:00Z",
  updated_at: "2026-07-09T00:00:01Z",
};

function badgeStep(output: Record<string, unknown>, overrides: Partial<StepResult> = {}): StepResult {
  return {
    step_id: 8,
    action_id: "issue_learncard_badge",
    status: "succeeded",
    attempt: 1,
    output,
    error: null,
    started_at: "2026-07-09T00:00:02Z",
    finished_at: "2026-07-09T00:00:03Z",
    ...overrides,
  };
}

const fullCredential = {
  issuer: { id: "did:web:learncard.example/issuer" },
  credentialSubject: {
    id: "did:key:z6MkRecipient",
    achievement: {
      name: "Introduction to Accounting",
      description: "Awarded for completing the Introduction to Accounting course.",
    },
  },
};

describe("BadgeViewer", () => {
  afterEach(() => {
    cleanup();
  });

  test("populated: renders the certificate art, watermark, achievement title, and recipient", () => {
    render(
      <BadgeViewer
        execution={{
          ...baseExecution,
          steps: [badgeStep({ result: { issued_credential: fullCredential } })],
        }}
      />,
    );

    expect(screen.getByText("Introduction to Accounting")).toBeTruthy();
    expect(screen.getByText("did:key:z6MkRecipient")).toBeTruthy();
    const button = screen.getByRole("button", { name: /Introduction to Accounting/ });
    expect(button.className).toContain("badge-certificate");
    expect(button.querySelector("img")).toBeTruthy();
  });

  test("populated: expanding reveals the human-readable fields and the raw credential JSON behind 'View raw'", () => {
    const { container } = render(
      <BadgeViewer
        execution={{
          ...baseExecution,
          steps: [badgeStep({ result: { issued_credential: fullCredential } })],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Introduction to Accounting/ }));
    expect(screen.getByText("Awarded for completing the Introduction to Accounting course.")).toBeTruthy();
    expect(screen.getByText("did:web:learncard.example/issuer")).toBeTruthy();

    expect(container.querySelector("pre")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "View raw" }));
    // The recipient DID also legitimately appears in the collapsed trigger and the
    // human-readable "recipient" row, so assert on the raw <pre> directly rather
    // than via getByText (which would ambiguate across those other occurrences).
    expect(container.querySelector("pre")?.textContent).toContain("did:key:z6MkRecipient");
  });

  test("varying structure: missing description and an extra unknown field don't crash — present fields render, extra field surfaces only in raw JSON", () => {
    const credential = {
      issuer: { id: "did:web:learncard.example/issuer" },
      credentialSubject: {
        id: "did:key:z6MkRecipient",
        achievement: { name: "Introduction to Accounting" },
      },
      proof: { type: "stub", futureField: "mystery-value" },
    };
    render(
      <BadgeViewer
        execution={{
          ...baseExecution,
          steps: [badgeStep({ result: { issued_credential: credential } })],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Introduction to Accounting/ }));
    expect(screen.queryByText("description")).toBeNull();
    expect(screen.queryByText(/mystery-value/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "View raw" }));
    expect(screen.getByText(/mystery-value/)).toBeTruthy();
  });

  test("graceful null: renders nothing when no issue_learncard_badge step succeeded", () => {
    const { container } = render(
      <BadgeViewer
        execution={{
          ...baseExecution,
          steps: [badgeStep({ result: { issued_credential: fullCredential } }, { status: "failed" })],
        }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  test("graceful null: renders nothing when the succeeded step has no issued_credential", () => {
    const { container } = render(
      <BadgeViewer
        execution={{
          ...baseExecution,
          steps: [badgeStep({ result: {} })],
        }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
