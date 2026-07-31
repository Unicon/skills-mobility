import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { ResetDemoButton } from "./ResetDemoButton";

describe("ResetDemoButton", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function stubFetch(body: unknown) {
    const calls: string[] = [];
    const spy = async (input: RequestInfo | URL) => {
      calls.push(String(input));
      return new Response(JSON.stringify(body), { status: 200 });
    };
    vi.stubGlobal("fetch", spy);
    return calls;
  }

  test("confirm → POSTs /demo/reset and reports success", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const calls = stubFetch({ ok: true, event_consumer: "reset" });

    render(<ResetDemoButton />);
    fireEvent.click(screen.getByRole("button", { name: /reset demo/i }));

    await waitFor(() => expect(screen.getByText("Reset ✓")).toBeTruthy());
    expect(calls).toEqual(["/demo/reset"]);
  });

  test("declined confirm makes no request", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const calls = stubFetch({ ok: true });

    render(<ResetDemoButton />);
    fireEvent.click(screen.getByRole("button", { name: /reset demo/i }));

    expect(calls).toEqual([]);
  });

  test("a cascade hop that did not clear is reported as partial, not success", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    stubFetch({ ok: true, event_consumer: "unreachable" });

    render(<ResetDemoButton />);
    fireEvent.click(screen.getByRole("button", { name: /reset demo/i }));

    await waitFor(() => expect(screen.getByText(/Partial reset/)).toBeTruthy());
  });
});
