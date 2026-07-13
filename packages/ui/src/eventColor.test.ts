import { describe, expect, test } from "vitest";
import { eventColor } from "./eventColor";

describe("eventColor", () => {
  test("maps known event types to their telemetry color", () => {
    expect(eventColor("skill_mastered")).toBe("var(--evt-skill)");
    expect(eventColor("course_completed")).toBe("var(--evt-course)");
    expect(eventColor("badge_awarded")).toBe("var(--evt-badge)");
  });

  test("maps digital_credential to --evt-credential", () => {
    expect(eventColor("digital_credential")).toBe("var(--evt-credential)");
  });

  test("falls back to the faint ink color for unknown event types", () => {
    expect(eventColor("something_unmapped")).toBe("var(--ink-faint)");
  });
});
