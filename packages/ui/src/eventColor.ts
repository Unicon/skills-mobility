const COLORS: Record<string, string> = {
  skill_mastered: "var(--evt-skill)",
  course_completed: "var(--evt-course)",
  badge_awarded: "var(--evt-badge)",
  digital_credential: "var(--evt-credential)",
};

export function eventColor(eventType: string): string {
  return COLORS[eventType] ?? "var(--ink-faint)";
}
