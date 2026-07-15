import type { EventEnvelope } from "@skills-mobility/contracts";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const useReducedMotionMock = vi.fn();
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => useReducedMotionMock() };
});

const { EnvelopeModal } = await import("./EnvelopeModal");

const envelope: EventEnvelope = {
  metadata: {
    event_name: "skill_mastered",
    event_time: "2026-07-09T00:00:00Z",
    producer: "mock-lms",
    user_id: "user_1",
    context_type: "Course",
    context_id: "course_1",
    event_id: "evt_1",
    correlation_id: "corr_1",
    action_id: "action_1",
  },
  body: {},
};

describe("EnvelopeModal", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("animates in from a hidden state by default", () => {
    useReducedMotionMock.mockReturnValue(false);
    render(<EnvelopeModal envelope={envelope} onClose={() => {}} onCopy={() => {}} />);

    const modal = document.querySelector(".modal") as HTMLElement;
    expect(modal.style.opacity).toBe("0");
  });

  test("skips the enter animation when prefers-reduced-motion is set (NFR-AU-5)", () => {
    useReducedMotionMock.mockReturnValue(true);
    render(<EnvelopeModal envelope={envelope} onClose={() => {}} onCopy={() => {}} />);

    const modal = document.querySelector(".modal") as HTMLElement;
    expect(modal.style.opacity).not.toBe("0");
  });
});
