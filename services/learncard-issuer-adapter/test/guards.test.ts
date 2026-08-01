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

  it("replaces a pre-registered re-throwing listener (AWS managed runtime)", async () => {
    // Reproduces the Lambda 502: the AWS Node runtime registers its own
    // unhandledRejection listener that re-throws, so it fires first and kills
    // the sandbox before the guard runs. Installing the guard must displace it.
    const warn = vi.spyOn(logger, "warn").mockImplementation(() => {});
    process.on("unhandledRejection", (reason) => {
      throw reason;
    });
    const { installCrashGuards } = await import("../src/guards");
    installCrashGuards();

    expect(() =>
      process.emit(
        "unhandledRejection",
        new Error("TRPCClientError: Unable to transform response from server"),
        Promise.resolve(),
      ),
    ).not.toThrow();

    expect(process.listenerCount("unhandledRejection")).toBe(1);
    expect(warn).toHaveBeenCalledWith(
      "unhandled promise rejection (kept alive)",
      expect.objectContaining({ reason: expect.stringContaining("transform response") }),
    );
  });
});
