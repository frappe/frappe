// The save dialog for compile errors, from the server's error entry to what the reader sees.
import { describe, expect, it } from "vitest";
import { createApp, h } from "vue";
import { readEnvelope, type ApiError } from "@framework/ui/api";
import { codeErrorFrames } from "../codeErrorFrames";
import CodeErrorsDialog from "../dialogs/CodeErrorsDialog.vue";

const SCRIPT = [
  "export default {",
  "  components: {",
  "    Badge: {",
  "\t\ttemplate: `<div><span></div>`,",
  "    },",
  "  },",
  "};",
].join("\n");

const FIELDS = [{ fieldname: "script", fieldtype: "Code", label: "Script" }];

function compileError(): ApiError {
  const body = {
    errors: [
      {
        type: "TemplateCompileError",
        title: "This script does not compile",
        message: "Line 4, column 19: Element is missing end tag.",
        code_errors: [
          { field: "script", line: 4, column: 19, message: "Element is missing end tag." },
          { field: "script", line: 1, column: 1, message: "A first-line error." },
        ],
      },
    ],
  };
  try {
    readEnvelope(body, 417);
  } catch (error) {
    return error as ApiError;
  }
  throw new Error("readEnvelope did not throw");
}

describe("codeErrorFrames", () => {
  it("keeps the line before and after, with a caret indent that keeps tabs", () => {
    const [frame, first] = codeErrorFrames(compileError().codeErrors!, { script: SCRIPT }, FIELDS);
    expect(frame).toMatchObject({ label: "Script", line: 4, column: 19 });
    expect(frame.lines.map((row) => row.number)).toEqual([3, 4, 5]);
    expect(frame.lines[1].text).toBe("\t\ttemplate: `<div><span></div>`,");
    expect(frame.indent).toBe("\t\t" + " ".repeat(16));
    expect(first.lines.map((row) => row.number)).toEqual([1, 2]);
  });

  it("names the field by its fieldname when the meta has no label", () => {
    const [frame] = codeErrorFrames(compileError().codeErrors!, { script: SCRIPT }, undefined);
    expect(frame.label).toBe("script");
  });
});

describe("CodeErrorsDialog", () => {
  it("lists each error with its place, its text and the lines around it", () => {
    const frames = codeErrorFrames(compileError().codeErrors!, { script: SCRIPT }, FIELDS);
    const host = document.createElement("div");
    const app = createApp({ render: () => h(CodeErrorsDialog, { frames, close: () => {} }) });
    app.mount(host);

    const sections = host.querySelectorAll("[data-code-error]");
    expect(sections).toHaveLength(2);
    const text = sections[0].textContent!;
    expect(text).toContain("Script, line 4, column 19");
    expect(text).toContain("Element is missing end tag.");
    expect(text).toContain("Badge: {");
    expect(text).toContain("template: `<div><span></div>`,");
    expect(text).toContain("},");
    expect(sections[0].querySelector("pre")!.textContent).toContain(`\t\t${" ".repeat(16)}^`);
    app.unmount();
  });
});
