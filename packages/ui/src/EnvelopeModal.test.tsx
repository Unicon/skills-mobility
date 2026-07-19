import type { EventEnvelope } from "@skills-mobility/contracts";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

  test("exposes dialog semantics with the event name as the accessible name (issue #71)", () => {
    useReducedMotionMock.mockReturnValue(true);
    render(<EnvelopeModal envelope={envelope} onClose={() => {}} onCopy={() => {}} />);

    expect(screen.getByRole("dialog", { name: envelope.metadata.event_name })).toBeTruthy();
  });

  test("closes on Escape (issue #71)", () => {
    useReducedMotionMock.mockReturnValue(true);
    const onClose = vi.fn();
    render(<EnvelopeModal envelope={envelope} onClose={onClose} onCopy={() => {}} />);

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("restores focus to the element that opened it, on close (issue #71)", async () => {
    useReducedMotionMock.mockReturnValue(true);
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();
    expect(document.activeElement).toBe(opener);

    const { unmount } = render(<EnvelopeModal envelope={envelope} onClose={() => {}} onCopy={() => {}} />);
    expect(document.activeElement).not.toBe(opener);

    unmount();
    // Radix's FocusScope restores focus inside a setTimeout(…, 0), not synchronously on unmount.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(document.activeElement).toBe(opener);

    opener.remove();
  });
});
