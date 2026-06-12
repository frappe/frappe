import { describe, expect, it } from "vitest";
import { createApp } from "vue";
import CodeEditor from "../CodeEditor.vue";
import CodePreview from "../CodePreview.vue";
import { fieldtypeToLanguage } from "../languages";
import type { FieldMeta } from "../../FormLayout/types";

const field = (over: Partial<FieldMeta>): FieldMeta => ({
  fieldname: "f",
  fieldtype: "Data",
  ...over,
});

describe("CodeEditor module", () => {
  // The writer lazy-loads CodeMirror in `onMounted` and CodeMirror measures
  // layout on mount, which a headless DOM (happy-dom/jsdom) can't render — so we
  // only assert the component imports cleanly as a valid SFC, not mount/measure.
  it("CodeEditor imports as a valid component", () => {
    expect(CodeEditor).toBeTypeOf("object");
  });

  it("CodePreview renders sanitized markdown", () => {
    const host = document.createElement("div");
    const app = createApp(CodePreview, {
      modelValue: "# Title",
      language: "markdown",
    });
    app.mount(host);
    expect(host.innerHTML).toContain("<h1");
    expect(host.textContent).toContain("Title");
    app.unmount();
  });

  it("CodePreview renders sanitized html", () => {
    const host = document.createElement("div");
    const app = createApp(CodePreview, {
      modelValue: "<p>hi</p><script>alert(1)</script>",
      language: "html",
    });
    app.mount(host);
    expect(host.innerHTML).toContain("<p>hi</p>");
    // The script tag is stripped by DOMPurify.
    expect(host.innerHTML).not.toContain("alert(1)");
    app.unmount();
  });

  it("CodePreview renders nothing for non-preview languages", () => {
    const host = document.createElement("div");
    const app = createApp(CodePreview, {
      modelValue: "const a = 1;",
      language: "javascript",
    });
    app.mount(host);
    expect(host.textContent).toBe("");
    app.unmount();
  });

  it("maps fieldtypes to CodeMirror languages", () => {
    expect(fieldtypeToLanguage(field({ fieldtype: "JSON" }))).toBe("json");
    expect(fieldtypeToLanguage(field({ fieldtype: "Markdown Editor" }))).toBe(
      "markdown"
    );
    expect(fieldtypeToLanguage(field({ fieldtype: "HTML Editor" }))).toBe(
      "html"
    );
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "Python" }))
    ).toBe("python");
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "SQL" }))
    ).toBe("sql");
    // SCSS / YAML / XML now have their own language packages.
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "SCSS" }))
    ).toBe("scss");
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "YAML" }))
    ).toBe("yaml");
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "XML" }))
    ).toBe("xml");
    // Unknown / empty options fall through to plain.
    expect(fieldtypeToLanguage(field({ fieldtype: "Data" }))).toBe("plain");
    expect(
      fieldtypeToLanguage(field({ fieldtype: "Code", options: "brainfuck" }))
    ).toBe("plain");
  });

  it("normalizes Code option aliases (py/js/yml…) case-insensitively", () => {
    const lang = (options: string) =>
      fieldtypeToLanguage(field({ fieldtype: "Code", options }));
    expect(lang("py")).toBe("python");
    expect(lang("JS")).toBe("javascript");
    expect(lang("node")).toBe("javascript");
    expect(lang("yml")).toBe("yaml");
    expect(lang("md")).toBe("markdown");
    expect(lang("postgresql")).toBe("sql");
    expect(lang("sass")).toBe("scss");
    // Jinja-family templates highlight as HTML.
    expect(lang("jinja2")).toBe("html");
    // Surrounding whitespace and mixed case are tolerated.
    expect(lang("  Python  ")).toBe("python");
  });
});
