import type { ExecutionMetadata } from "@skills-mobility/contracts";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { EventDetailCard } from "./EventDetailCard";

const execution: ExecutionMetadata = {
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

describe("EventDetailCard", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders a reconstructed event envelope using the execution's real fields", () => {
    render(<EventDetailCard execution={execution} />);
    expect(screen.getByText(/skill_mastered/)).toBeTruthy();
    expect(screen.getByText(/corr_1/)).toBeTruthy();
    expect(screen.getByText(/exec_1/)).toBeTruthy();
  });

  test("discloses that the event body is reconstructed, not the persisted raw event", () => {
    render(<EventDetailCard execution={execution} />);
    expect(screen.getByText(/isn't persisted/)).toBeTruthy();
  });
});
