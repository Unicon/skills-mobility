import type { StepResult } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { StepRow } from "./StepRow";

function step(overrides: Partial<StepResult>): StepResult {
  return {
    step_id: 1,
    action_id: "resolve_learncard_profile",
    status: "succeeded",
    attempt: 1,
    output: {},
    error: null,
    started_at: "2026-07-09T00:00:00Z",
    finished_at: "2026-07-09T00:00:01Z",
    ...overrides,
  };
}

describe("StepRow", () => {
  afterEach(() => {
    cleanup();
  });

  test.each([
    "generate_credential_template_mapping",
    "generate_credential_template_synthesis",
    "generate_issuer_payload_mapping",
    "generate_issuer_payload_synthesis",
    "generate_learncard_wallet_payload_mapping",
    "generate_smartresume_payload_mapping",
  ])("shows the AI marker for the AI-backed action %s", (actionId) => {
    render(<StepRow step={step({ action_id: actionId })} activePhase={null} onActiveChange={() => {}} />);
    expect(screen.getByRole("img", { name: "AI-generated step" })).toBeTruthy();
  });

  test.each([
    "execute_credential_template_translation",
    "execute_issuer_payload_translation",
    "execute_learncard_wallet_payload_translation",
    "execute_smartresume_payload_translation",
  ])("shows a phase tag but no AI marker for the deterministic transformation step %s", (actionId) => {
    render(<StepRow step={step({ action_id: actionId })} activePhase={null} onActiveChange={() => {}} />);
    expect(screen.queryByRole("img", { name: "AI-generated step" })).toBeNull();
    expect(screen.getByText("field mapping")).toBeTruthy();
  });

  test("shows the right phase label for a workflow_actions_plan step", () => {
    render(
      <StepRow
        step={step({ action_id: "resolve_learncard_profile" })}
        activePhase={null}
        onActiveChange={() => {}}
      />,
    );
    expect(screen.getByText("workflow actions")).toBeTruthy();
  });

  test("shows no phase tag for an unknown action_id", () => {
    render(<StepRow step={step({ action_id: "some_future_action" })} activePhase={null} onActiveChange={() => {}} />);
    expect(screen.queryByText("workflow actions")).toBeNull();
    expect(screen.queryByText("field mapping")).toBeNull();
  });

  test("adds .highlighted only when activePhase matches the row's phase", () => {
    const { rerender } = render(
      <StepRow
        step={step({ action_id: "resolve_learncard_profile" })}
        activePhase={null}
        onActiveChange={() => {}}
      />,
    );
    expect(screen.getByText("resolve_learncard_profile").closest("button")?.className).not.toContain(
      "highlighted",
    );

    rerender(
      <StepRow
        step={step({ action_id: "resolve_learncard_profile" })}
        activePhase="workflow_actions_plan"
        onActiveChange={() => {}}
      />,
    );
    expect(screen.getByText("resolve_learncard_profile").closest("button")?.className).toContain(
      "highlighted",
    );
  });

  test("fires onActiveChange with the step's phase on hover/focus, and null on leave/blur", () => {
    const onActiveChange = vi.fn();
    render(
      <StepRow
        step={step({ action_id: "resolve_learncard_profile" })}
        activePhase={null}
        onActiveChange={onActiveChange}
      />,
    );
    const button = screen.getByText("resolve_learncard_profile").closest("button")!;

    fireEvent.mouseEnter(button);
    expect(onActiveChange).toHaveBeenLastCalledWith("workflow_actions_plan");
    fireEvent.mouseLeave(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(null);
    fireEvent.focus(button);
    expect(onActiveChange).toHaveBeenLastCalledWith("workflow_actions_plan");
    fireEvent.blur(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(null);
  });

  test("raw-JSON disclosure still opens", () => {
    render(
      <StepRow
        step={step({ action_id: "resolve_learncard_profile", output: { foo: "bar" } })}
        activePhase={null}
        onActiveChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByText("resolve_learncard_profile").closest("button")!);
    expect(screen.getByText(/"foo": "bar"/)).toBeTruthy();
  });
});
