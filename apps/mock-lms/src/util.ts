const COLORS: Record<string, string> = {
  skill_mastered: "var(--evt-skill)",
  course_completed: "var(--evt-course)",
  badge_awarded: "var(--evt-badge)",
  credential_eligible: "var(--evt-credential)",
};

export function eventColor(eventType: string): string {
  return COLORS[eventType] ?? "var(--ink-faint)";
}

export function shortId(id: string, keep = 6): string {
  const i = id.indexOf("_");
  const head = i >= 0 ? id.slice(0, i + 1) : "";
  const tail = id.slice(i + 1);
  return `${head}${tail.slice(0, keep)}…`;
}

export function clockTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour12: false }) + "." + String(d.getMilliseconds()).padStart(3, "0");
}

export async function copy(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}

/** Tiny JSON syntax highlighter for the envelope modal. */
export function highlightJson(value: unknown): string {
  const json = JSON.stringify(value, null, 2)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?)/g,
    (match) => {
      if (/:$/.test(match)) return `<span class="jk">${match}</span>`;
      if (/^(true|false|null)$/.test(match)) return `<span class="jb">${match}</span>`;
      if (/^"/.test(match)) return `<span class="js">${match}</span>`;
      return match;
    },
  );
}
