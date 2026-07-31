import { ThemeToggle } from "@skills-mobility/ui";

export function Header() {
  return (
    <header className="topbar">
      <div className="wordmark">
        <b>
          MOCK<span>·</span>LMS
        </b>
        <small>Source System — Skills Mobility POC</small>
      </div>

      <div className="topbar-spacer" />

      <div className="statuschip" title="The Mock LMS stands in for the source LMS (Canvas-modeled)">
        <span className="dot" style={{ background: "var(--gold)" }} />
        SOURCE SYSTEM
      </div>
      <ThemeToggle storageKey="mock-lms-theme" />
    </header>
  );
}
