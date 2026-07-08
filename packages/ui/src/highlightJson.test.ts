import { describe, expect, test } from "vitest";
import { highlightJson } from "./highlightJson";

describe("highlightJson", () => {
  test("wraps keys, strings, and booleans in span tags", () => {
    const html = highlightJson({ name: "Ada", active: true });
    expect(html).toContain('<span class="jk">"name":</span>');
    expect(html).toContain('<span class="js">"Ada"</span>');
    expect(html).toContain('<span class="jb">true</span>');
  });

  test("escapes HTML-significant characters", () => {
    const html = highlightJson({ note: "<script>&</script>" });
    expect(html).not.toContain("<script>");
    expect(html).toContain("&lt;script&gt;");
  });

  test("degrades gracefully instead of throwing on a circular value", () => {
    const circular: Record<string, unknown> = {};
    circular.self = circular;

    expect(() => highlightJson(circular)).not.toThrow();
    expect(highlightJson(circular)).toContain("Unable to render payload");
  });

  test("truncates very large payloads instead of rendering the whole thing", () => {
    const huge = { items: Array.from({ length: 5000 }, (_, i) => `item-${i}`) };
    const html = highlightJson(huge);

    expect(html).toContain("truncated");
    expect(html.length).toBeLessThan(JSON.stringify(huge).length);
  });
});
