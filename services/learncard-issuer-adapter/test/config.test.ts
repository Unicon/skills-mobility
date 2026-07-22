import { createHash } from "node:crypto";

import { afterEach, describe, expect, it } from "vitest";

import { deriveSeed, loadConfig } from "../src/config";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("seed resolution", () => {
  it("derives the seed from SEED_LABEL using the tools/learncard-demo scheme", () => {
    delete process.env.SECURE_SEED;
    process.env.SEED_LABEL = "organization";
    const seed = loadConfig().secureSeed;
    // Same derivation as tools/learncard-demo/derive.mjs (ADR-0020) — a fixed
    // identity is reproducible from a public label, no raw seed committed.
    expect(seed).toBe(createHash("sha256").update("skills-mobility-demo:organization").digest("hex"));
    expect(seed).toMatch(/^[0-9a-f]{64}$/);
    expect(deriveSeed("organization")).toBe(seed);
  });

  it("uses a raw SECURE_SEED verbatim, overriding SEED_LABEL", () => {
    process.env.SECURE_SEED = "deadbeef";
    process.env.SEED_LABEL = "organization";
    expect(loadConfig().secureSeed).toBe("deadbeef");
  });

  it("is null when neither SECURE_SEED nor SEED_LABEL is set", () => {
    delete process.env.SECURE_SEED;
    delete process.env.SEED_LABEL;
    expect(loadConfig().secureSeed).toBeNull();
  });
})
