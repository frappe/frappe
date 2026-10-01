// Compile errors from the host, drawn as lint marks in the Code field.
import { forEachDiagnostic } from "@codemirror/lint";
import { Text } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";
import type { CodeError } from "../../../api/envelope";
import CodeEditorField from "../CodeEditorField.vue";
import { diagnosticsFor } from "../codeErrorMarks";
import { CodeErrorsKey, ParentDocKey } from "../types";

const SCRIPT = "export default {\n  template: `<div><span></div>`,\n};";
const ERROR: CodeError = {
  field: "script",
  line: 2,
  column: 19,
  message: "Element is missing end tag.",
};
const AT = SCRIPT.indexOf("<span>");

// Mounted with Vue's own `createApp`: this package has no `@vue/test-utils`.
let app: App | null = null;
let host: HTMLElement;

afterEach(() => {
  app?.unmount();
  app = null;
  host.remove();
});

async function mountField(errors: CodeError[], inRow = false) {
  const codeErrors = ref<CodeError[]>(errors);
  const field = { fieldname: "script", fieldtype: "Code", label: "Script" };
  host = document.body.appendChild(document.createElement("div"));
  app = createApp({ render: () => h(CodeEditorField, { field, modelValue: SCRIPT }) });
  app.provide(CodeErrorsKey, codeErrors);
  if (inRow) app.provide(ParentDocKey, ref({}));
  app.mount(host);
  await nextTick();
  const view = EditorView.findFromDOM(host.querySelector(".cm-editor") as HTMLElement)!;
  return { codeErrors, view };
}

function marks(view: EditorView) {
  const found: { from: number; message: string }[] = [];
  forEachDiagnostic(view.state, (d, from) => found.push({ from, message: d.message }));
  return found;
}

describe("Code field compile errors", () => {
  it("marks the line and column, with a gutter icon, and puts the cursor there", async () => {
    const { view } = await mountField([ERROR]);
    await vi.waitFor(() => expect(marks(view)).toEqual([{ from: AT, message: ERROR.message }]));
    expect(view.state.selection.main.head).toBe(AT);
    await vi.waitFor(() => {
      expect(host.querySelector(".cm-lintRange-error")).not.toBeNull();
      expect(host.querySelector(".cm-lint-marker-error")).not.toBeNull();
    });
  });

  it("moves a mark with an edit and clears it on the next save", async () => {
    const { codeErrors, view } = await mountField([]);
    codeErrors.value = [ERROR];
    await vi.waitFor(() => expect(marks(view)).toHaveLength(1));

    view.dispatch({ changes: { from: 0, insert: "// note\n" } });
    expect(marks(view)[0].from).toBe(AT + "// note\n".length);

    codeErrors.value = [];
    await vi.waitFor(() => expect(marks(view)).toEqual([]));
  });

  it("marks only the field the error names", async () => {
    const { view } = await mountField([{ ...ERROR, field: "other" }]);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(marks(view)).toEqual([]);
  });

  it("takes no marks inside a child row", async () => {
    const { view } = await mountField([ERROR], true);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(marks(view)).toEqual([]);
  });
});

describe("diagnosticsFor", () => {
  it("lands a line or column past the text at its end", () => {
    const doc = Text.of(["ab", "cd"]);
    const at = (line: number, column: number) =>
      diagnosticsFor(doc, [{ ...ERROR, line, column }])[0];
    expect(at(2, 2)).toMatchObject({ from: 4, to: 5 });
    expect(at(2, 9)).toMatchObject({ from: 5, to: 5 });
    expect(at(7, 1)).toMatchObject({ from: 3, to: 4 });
    expect(at(0, 0)).toMatchObject({ from: 0, to: 1 });
  });
});
