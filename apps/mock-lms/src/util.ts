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
