import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { useTheme } from "./useTheme";

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

describe("useTheme", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", fakeLocalStorage());
    document.documentElement.classList.remove("light", "dark");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.documentElement.classList.remove("light", "dark");
  });

  test("defaults to dark when the DOM class is unset", () => {
    const { result } = renderHook(() => useTheme("admin-theme"));
    expect(result.current.theme).toBe("dark");
  });

  test("reads the initial theme from the DOM class the blocking script already set", () => {
    document.documentElement.classList.add("light");
    const { result } = renderHook(() => useTheme("admin-theme"));
    expect(result.current.theme).toBe("light");
  });

  test("toggle() flips the <html> class and persists to localStorage", () => {
    document.documentElement.classList.add("dark");
    const { result } = renderHook(() => useTheme("admin-theme"));

    act(() => {
      result.current.toggle();
    });

    expect(result.current.theme).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("admin-theme")).toBe("light");

    act(() => {
      result.current.toggle();
    });

    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("admin-theme")).toBe("dark");
  });
});
