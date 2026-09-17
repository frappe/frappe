/**
 * @vitest-environment jsdom
 *
 * CodePreview is the sanitize-before-render half of the code field, pure enough
 * to mount in jsdom. The writer half is CodeMirror, which measures layout on
 * mount and so cannot be asserted here.
 */
import { describe, expect, it } from "vitest";
import { createApp } from "vue";
import CodePreview from "../CodePreview.vue";

function render(props: Record<string, unknown>) {
  const host = document.createElement("div");
  const app = createApp(CodePreview, props);
  app.mount(host);
  const html = host.innerHTML;
  const text = host.textContent ?? "";
  app.unmount();
  return { html, text };
}

describe("CodePreview", () => {
  it("renders sanitized markdown", () => {
    const { html, text } = render({ modelValue: "# Title", language: "markdown" });
    expect(html).toContain("<h1");
    expect(text).toContain("Title");
  });

  it("renders sanitized html", () => {
    const { html } = render({
      modelValue: "<p>hi</p><script>alert(1)</script>",
      language: "html",
    });
    expect(html).toContain("<p>hi</p>");
    // The script tag is stripped by DOMPurify.
    expect(html).not.toContain("alert(1)");
  });

  it("strips event-handler attributes from markdown-embedded html", () => {
    const { html } = render({
      modelValue: '<img src="x" onerror="alert(1)">',
      language: "markdown",
    });
    expect(html).not.toContain("onerror");
  });

  it("renders nothing for non-preview languages", () => {
    expect(render({ modelValue: "const a = 1;", language: "javascript" }).text).toBe("");
    expect(render({ modelValue: "{}", language: "json" }).text).toBe("");
    expect(render({ modelValue: "x", language: "plain" }).text).toBe("");
  });

  it("keeps the container for an empty preview language", () => {
    // The consumer's min-height/border has to hold instead of collapsing.
    expect(render({ modelValue: "", language: "markdown" }).html).toContain("<div");
  });
});
