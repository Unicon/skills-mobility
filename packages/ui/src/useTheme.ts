import { useState } from "react";

export type Theme = "light" | "dark";

/** Theme state backed by the <html> class the app's blocking bootstrap script
 * already set pre-paint (no flash), persisted per app under `storageKey` so
 * the two consoles' choices don't clobber each other. */
export function useTheme(storageKey: string): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(
    document.documentElement.classList.contains("light") ? "light" : "dark",
  );

  const toggle = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.classList.remove(theme);
    document.documentElement.classList.add(next);
    localStorage.setItem(storageKey, next);
    setTheme(next);
  };

  return { theme, toggle };
}
