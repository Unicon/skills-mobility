import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { ClampedBlock } from "./ClampedBlock";

function mockScrollHeight(height: number) {
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", {
    configurable: true,
    value: height,
  });
}

describe("ClampedBlock", () => {
  afterEach(() => {
    cleanup();
    mockScrollHeight(0);
  });

  test("shows no toggle when content fits within maxHeight", () => {
    mockScrollHeight(50);
    render(<ClampedBlock maxHeight={160}>short content</ClampedBlock>);
    expect(screen.queryByRole("button")).toBeNull();
  });

  test("shows a Show more toggle when content overflows maxHeight", () => {
    mockScrollHeight(400);
    render(<ClampedBlock maxHeight={160}>long content</ClampedBlock>);
    expect(screen.getByRole("button", { name: "Show more" })).toBeTruthy();
  });

  test("toggling switches the label to Show less and removes the height clamp", () => {
    mockScrollHeight(400);
    render(<ClampedBlock maxHeight={160}>long content</ClampedBlock>);
    fireEvent.click(screen.getByRole("button", { name: "Show more" }));
    expect(screen.getByRole("button", { name: "Show less" })).toBeTruthy();
  });
});
