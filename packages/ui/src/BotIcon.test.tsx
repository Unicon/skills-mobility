import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { BotIcon } from "./BotIcon";

describe("BotIcon", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders an svg that is hidden from assistive tech", () => {
    const { container } = render(<BotIcon />);
    const svg = container.querySelector("svg");
    expect(svg).toBeTruthy();
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });

  test("defaults to a 32x30 size", () => {
    const { container } = render(<BotIcon />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("32");
    expect(svg?.getAttribute("height")).toBe("30");
  });

  test("respects a custom size, preserving aspect ratio", () => {
    const { container } = render(<BotIcon size={14} />);
    const svg = container.querySelector("svg");
    expect(svg?.getAttribute("width")).toBe("14");
    expect(svg?.getAttribute("height")).toBe(String((14 * 30) / 32));
  });
});
