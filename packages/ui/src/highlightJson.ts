const MAX_JSON_CHARS = 20_000;

/** Tiny JSON syntax highlighter for the envelope viewer. Degrades gracefully on
 * non-serializable (e.g. circular) values and truncates very large payloads. */
export function highlightJson(value: unknown): string {
  let json: string;
  try {
    json = JSON.stringify(value, null, 2) ?? "undefined";
  } catch {
    return '<span class="jb">Unable to render payload (circular or non-serializable value)</span>';
  }

  const truncated = json.length > MAX_JSON_CHARS;
  const source = truncated ? json.slice(0, MAX_JSON_CHARS) : json;

  const escaped = source
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  const highlighted = escaped.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?)/g,
    (match) => {
      if (/:$/.test(match)) return `<span class="jk">${match}</span>`;
      if (/^(true|false|null)$/.test(match)) return `<span class="jb">${match}</span>`;
      if (/^"/.test(match)) return `<span class="js">${match}</span>`;
      return match;
    },
  );

  return truncated
    ? `${highlighted}\n<span class="jb">… truncated (${json.length.toLocaleString()} chars total)</span>`
    : highlighted;
}
