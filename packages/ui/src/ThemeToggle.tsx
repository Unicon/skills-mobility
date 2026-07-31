import { MoonIcon, SunIcon } from "@radix-ui/react-icons";
import { useTheme } from "./useTheme";

export function ThemeToggle({ storageKey }: { storageKey: string }) {
  const { theme, toggle } = useTheme(storageKey);
  const isLight = theme === "light";

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={isLight ? "Switch to dark theme" : "Switch to light theme"}
    >
      {isLight ? <MoonIcon aria-hidden="true" /> : <SunIcon aria-hidden="true" />}
    </button>
  );
}
