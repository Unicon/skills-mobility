import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";

const useReducedMotionMock = vi.fn();
vi.mock("motion/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("motion/react")>();
  return { ...actual, useReducedMotion: () => useReducedMotionMock() };
});

const { FlowConnector } = await import("./FlowConnector");

describe("FlowConnector", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("renders a solid connector for the populated state", () => {
    const { container } = render(<FlowConnector state="populated" />);
    expect(container.querySelector(".flow-connector-populated")).toBeTruthy();
    expect(container.querySelector(".flow-connector-pending")).toBeFalsy();
  });

  test("renders a dashed connector for the pending state", () => {
    const { container } = render(<FlowConnector state="pending" />);
    expect(container.querySelector(".flow-connector-pending")).toBeTruthy();
    expect(container.querySelector("line")).toBeTruthy();
  });

  test("animates the draw-in from zero pathLength by default", () => {
    useReducedMotionMock.mockReturnValue(false);
    const { container } = render(<FlowConnector state="populated" />);
    const line = container.querySelector("line") as SVGLineElement;
    expect(line.getAttribute("stroke-dasharray")).not.toBeNull();
  });

  test("skips the draw-in animation when prefers-reduced-motion is set", () => {
    useReducedMotionMock.mockReturnValue(true);
    const { container } = render(<FlowConnector state="populated" />);
    const line = container.querySelector("line") as SVGLineElement;
    expect(line.getAttribute("stroke-dashoffset")).toBe("0px");
  });
});
