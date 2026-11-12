// Markdown Editor is CodeMirror in a form and a plain multi-line input in a panel row.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h } from "vue";
import type { App } from "vue";
import { getFieldComponent } from "../fieldTypes";
import MarkdownEditorField from "../MarkdownEditorField.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function mount(panel: boolean | undefined) {
  const onInput = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(MarkdownEditorField, {
        field: { fieldname: "notes", fieldtype: "Markdown Editor", label: "Notes" },
        modelValue: "# Title\nbody",
        panel,
        "onUpdate:modelValue": onInput,
      }),
  });
  app.mount(host);
  return { root: host, onInput };
}

describe("MarkdownEditorField", () => {
  it("is the component registered for Markdown Editor", () => {
    expect(getFieldComponent("Markdown Editor")).toBe(MarkdownEditorField);
  });

  it("draws a plain textarea with the raw text in a panel row", async () => {
    const { root, onInput } = mount(true);
    const area = root.querySelector("textarea")!;
    expect(area.value).toBe("# Title\nbody");
    area.value = "# Title\nbody!";
    area.dispatchEvent(new Event("input"));
    await vi.waitFor(() => expect(onInput).toHaveBeenCalled());
    expect(onInput).toHaveBeenCalledWith("# Title\nbody!");
  });

  it("draws the code editor outside a panel", async () => {
    const { root } = mount(undefined);
    await vi.waitFor(() => expect(root.querySelector(".cm-editor")).not.toBeNull(), { timeout: 10_000 });
    expect(root.querySelector("textarea")).toBeNull();
  });
});
