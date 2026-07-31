import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ThemeToggle } from "./ThemeToggle";

// Node's own global `localStorage` (this Node version) shadows jsdom's
// window.localStorage and is non-functional here; stub a working one, same
// pattern api.test.ts uses for globalThis.fetch.
function fakeLocalStorage(): Storage {
  const store = new Map<string, string>();
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => store.set(key, value),
    removeItem: (key: string) => store.delete(key),
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  } as Storage;
}

describe("ThemeToggle", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", fakeLocalStorage());
    document.documentElement.classList.remove("light", "dark");
    document.documentElement.classList.add("dark");
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    document.documentElement.classList.remove("light", "dark");
  });

  test("renders an icon button labeled for the current theme", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Switch to light theme" });
    expect(button.querySelector("svg")).toBeTruthy();
  });

  test("clicking flips the theme, the DOM class, and the label", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to light theme" }));

    const button = screen.getByRole("button", { name: "Switch to dark theme" });
    expect(button.querySelector("svg")).toBeTruthy();
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });
});
