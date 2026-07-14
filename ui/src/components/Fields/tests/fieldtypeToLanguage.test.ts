import { describe, expect, it } from "vitest";
import { fieldtypeToLanguage } from "../fieldtypeToLanguage";
import type { FieldMeta } from "../types";

const field = (over: Partial<FieldMeta>): FieldMeta => ({
  fieldname: "f",
  fieldtype: "Data",
  ...over,
});

describe("fieldtypeToLanguage", () => {
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
