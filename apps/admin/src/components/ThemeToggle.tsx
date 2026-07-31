import { MoonIcon, SunIcon } from "@radix-ui/react-icons";
import { useTheme } from "../hooks/useTheme";

export function ThemeToggle() {
  const { theme, toggle } = useTheme();
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
