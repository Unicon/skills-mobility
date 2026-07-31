import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { DecisionNode } from "./DecisionNode";

describe("DecisionNode", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders a populated node and reports expanded state via aria-expanded", () => {
    render(
      <DecisionNode label="gate" confidence={0.9} state="populated" expanded onClick={() => {}} />,
    );
    const button = screen.getByRole("button", { name: "gate" });
    expect(button.getAttribute("aria-expanded")).toBe("true");
  });

  test("applies the selected/expanded class only when expanded, distinguishing it from other populated nodes", () => {
    const { rerender } = render(
      <DecisionNode label="gate" confidence={0.9} state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "gate" }).className).not.toContain("decision-node-expanded");

    rerender(
      <DecisionNode label="gate" confidence={0.9} state="populated" expanded onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "gate" }).className).toContain("decision-node-expanded");
  });

  test("writes the exact confidence percentage on a populated node", () => {
    render(
      <DecisionNode label="gate" confidence={0.98} state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByText("98%")).toBeTruthy();
  });

  test("renders a pending/ghost node with no confidence", () => {
    render(
      <DecisionNode
        label="delivery_targets"
        confidence={null}
        state="pending"
        expanded={false}
        onClick={() => {}}
      />,
    );
    const button = screen.getByRole("button", { name: "delivery_targets" });
    expect(button.className).toContain("decision-node-pending");
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("—")).toBeTruthy();
  });

  test("shows an em-dash instead of a percentage when a populated node has no confidence value", () => {
    render(
      <DecisionNode label="gate" confidence={null} state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByText("—")).toBeTruthy();
  });

  test("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(
      <DecisionNode label="gate" confidence={0.5} state="populated" expanded={false} onClick={onClick} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("adds decision-node-highlighted only when highlighted is true", () => {
    render(
      <DecisionNode
        label="gate"
        confidence={0.5}
        state="populated"
        expanded={false}
        onClick={() => {}}
        highlighted
      />,
    );
    expect(screen.getByRole("button", { name: "gate" }).className).toContain(
      "decision-node-highlighted",
    );
  });

  test("omitting highlighted keeps current behavior (no highlight class)", () => {
    render(
      <DecisionNode label="gate" confidence={0.5} state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "gate" }).className).not.toContain(
      "decision-node-highlighted",
    );
  });

  test("fires onActiveChange(true/false) on hover enter/leave and focus/blur", () => {
    const onActiveChange = vi.fn();
    render(
      <DecisionNode
        label="gate"
        confidence={0.5}
        state="populated"
        expanded={false}
        onClick={() => {}}
        onActiveChange={onActiveChange}
      />,
    );
    const button = screen.getByRole("button", { name: "gate" });

    fireEvent.mouseEnter(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(true);
    fireEvent.mouseLeave(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
    fireEvent.focus(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(true);
    fireEvent.blur(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
  });

  test("omitting onActiveChange does not throw on hover/focus", () => {
    render(
      <DecisionNode label="gate" confidence={0.5} state="populated" expanded={false} onClick={() => {}} />,
    );
    const button = screen.getByRole("button", { name: "gate" });
    expect(() => {
      fireEvent.mouseEnter(button);
      fireEvent.mouseLeave(button);
    }).not.toThrow();
  });
});
