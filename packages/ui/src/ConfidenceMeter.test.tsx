import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const useReducedMotionMock = vi.fn();
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => useReducedMotionMock() };
});

const { ConfidenceMeter } = await import("./ConfidenceMeter");

describe("ConfidenceMeter", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("animates the fill width in from zero by default", () => {
    useReducedMotionMock.mockReturnValue(false);
    render(<ConfidenceMeter value={0.7} />);
    const fill = document.querySelector(".confidence-meter-fill") as HTMLElement;
    expect(fill.style.width).toBe("0px");
  });

  test("skips the fill animation when prefers-reduced-motion is set", () => {
    useReducedMotionMock.mockReturnValue(true);
    render(<ConfidenceMeter value={0.7} />);
    const fill = document.querySelector(".confidence-meter-fill") as HTMLElement;
    expect(fill.style.width).not.toBe("0px");
  });

  test("renders a low-confidence value with the low tier", () => {
    render(<ConfidenceMeter value={0.2} label="Gate" />);
    expect(screen.getByText("20%")).toBeTruthy();
    expect(screen.getByText("Gate")).toBeTruthy();
  });

  test("renders a mid-confidence value with the mid tier", () => {
    const { container } = render(<ConfidenceMeter value={0.65} />);
    expect(container.querySelector('[data-tier="mid"]')).toBeTruthy();
    expect(screen.getByText("65%")).toBeTruthy();
  });

  test("renders a high-confidence value with the high tier", () => {
    const { container } = render(<ConfidenceMeter value={0.95} />);
    expect(container.querySelector('[data-tier="high"]')).toBeTruthy();
  });

  test("treats the 0.8 boundary as mid, not high", () => {
    const { container } = render(<ConfidenceMeter value={0.8} />);
    expect(container.querySelector('[data-tier="mid"]')).toBeTruthy();
  });

  test("clamps out-of-range values instead of crashing", () => {
    render(<ConfidenceMeter value={1.4} />);
    expect(screen.getByText("100%")).toBeTruthy();
  });
});
