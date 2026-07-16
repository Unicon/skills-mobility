import { afterEach, describe, expect, it, vi } from "vitest";
import { logger } from "../src/logger";

describe("installCrashGuards", () => {
  afterEach(() => {
    process.removeAllListeners("unhandledRejection");
    vi.restoreAllMocks();
  });

  it("logs a detached rejection and keeps the process alive (does not exit)", async () => {
    // Reproduces the e2e crash: a background LearnCloud handshake rejects outside
    // any await chain. Node would terminate by default; the guard must swallow it.
    const warn = vi.spyOn(logger, "warn").mockImplementation(() => {});
    const exit = vi.spyOn(process, "exit").mockImplementation((() => undefined) as never);
    const { installCrashGuards } = await import("../src/guards");
    installCrashGuards();

    process.emit(
      "unhandledRejection",
      new Error("TRPCClientError: Internal Server Error"),
      Promise.resolve(),
    );

    expect(warn).toHaveBeenCalledWith(
      "unhandled promise rejection (kept alive)",
      expect.objectContaining({ reason: expect.stringContaining("Internal Server Error") }),
    );
    expect(exit).not.toHaveBeenCalled();
  });
});
