import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { PipelineInfoNode } from "./PipelineInfoNode";

describe("PipelineInfoNode", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders a populated node with the given icon and label", () => {
    render(
      <PipelineInfoNode
        icon={<svg data-testid="icon" />}
        label="Event"
        state="populated"
        expanded={false}
        onClick={() => {}}
      />,
    );
    const button = screen.getByRole("button", { name: "Event" });
    expect(button.className).toContain("decision-node-populated");
    expect(screen.getByTestId("icon")).toBeTruthy();
  });

  test("renders a pending node dimmed, with no confidence text at all", () => {
    render(
      <PipelineInfoNode
        icon={<svg />}
        label="Wallet"
        state="pending"
        expanded={false}
        onClick={() => {}}
      />,
    );
    const button = screen.getByRole("button", { name: "Wallet" });
    expect(button.className).toContain("decision-node-pending");
    expect(screen.queryByText(/%/)).toBeNull();
  });

  test("applies the expanded class only when expanded", () => {
    const { rerender } = render(
      <PipelineInfoNode icon={<svg />} label="Wallet" state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Wallet" }).className).not.toContain(
      "decision-node-expanded",
    );

    rerender(
      <PipelineInfoNode icon={<svg />} label="Wallet" state="populated" expanded onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Wallet" }).className).toContain("decision-node-expanded");
  });

  test("calls onClick when clicked", () => {
    const onClick = vi.fn();
    render(
      <PipelineInfoNode icon={<svg />} label="Event" state="populated" expanded={false} onClick={onClick} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test("adds decision-node-highlighted only when highlighted is true", () => {
    render(
      <PipelineInfoNode
        icon={<svg />}
        label="Event"
        state="populated"
        expanded={false}
        onClick={() => {}}
        highlighted
      />,
    );
    expect(screen.getByRole("button", { name: "Event" }).className).toContain(
      "decision-node-highlighted",
    );
  });

  test("omitting highlighted keeps current behavior (no highlight class)", () => {
    render(
      <PipelineInfoNode icon={<svg />} label="Event" state="populated" expanded={false} onClick={() => {}} />,
    );
    expect(screen.getByRole("button", { name: "Event" }).className).not.toContain(
      "decision-node-highlighted",
    );
  });

  test("fires onActiveChange(true/false) on hover enter/leave and focus/blur", () => {
    const onActiveChange = vi.fn();
    render(
      <PipelineInfoNode
        icon={<svg />}
        label="Event"
        state="populated"
        expanded={false}
        onClick={() => {}}
        onActiveChange={onActiveChange}
      />,
    );
    const button = screen.getByRole("button", { name: "Event" });

    fireEvent.mouseEnter(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(true);
    fireEvent.mouseLeave(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
    fireEvent.focus(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(true);
    fireEvent.blur(button);
    expect(onActiveChange).toHaveBeenLastCalledWith(false);
  });
});
