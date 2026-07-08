import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { CopyableId } from "./CopyableId";

describe("CopyableId", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  test("renders as a real, keyboard-operable button", () => {
    render(<CopyableId value="corr_123" display="corr_123…" label="correlation id" />);
    const button = screen.getByRole("button", { name: "corr_123…" });
    expect(button.getAttribute("title")).toBe("Copy correlation id");
  });

  test("copies the value and calls onCopied on success", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onCopied = vi.fn();

    render(
      <CopyableId
        value="corr_123"
        display="corr_123…"
        label="correlation id"
        onCopied={onCopied}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    await vi.waitFor(() => expect(onCopied).toHaveBeenCalledWith("corr_123", "correlation id"));

    expect(writeText).toHaveBeenCalledWith("corr_123");
  });

  test("shows visible failure feedback when the clipboard write rejects", async () => {
    Object.assign(navigator, {
      clipboard: { writeText: vi.fn().mockRejectedValue(new Error("denied")) },
    });

    render(<CopyableId value="corr_123" display="corr_123…" label="correlation id" />);
    fireEvent.click(screen.getByRole("button"));

    await screen.findByRole("button", { name: "Copy failed" });
  });
});
