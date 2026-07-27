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
});
