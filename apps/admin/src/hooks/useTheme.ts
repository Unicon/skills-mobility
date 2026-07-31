import { useState } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "admin-theme";

export function useTheme(): { theme: Theme; toggle: () => void } {
  const [theme, setTheme] = useState<Theme>(
    document.documentElement.classList.contains("light") ? "light" : "dark",
  );

  const toggle = () => {
    const next: Theme = theme === "light" ? "dark" : "light";
    document.documentElement.classList.remove(theme);
    document.documentElement.classList.add(next);
    localStorage.setItem(STORAGE_KEY, next);
    setTheme(next);
  };

  return { theme, toggle };
}
