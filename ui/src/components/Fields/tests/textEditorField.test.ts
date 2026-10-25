// The Text Editor control: when it writes and commits, what it stores, what read-only loads,
// where an image goes, and how a grid cell shows it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import TextEditorField from "../TextEditorField.vue";
import TableField from "../TableField.vue";
import { getFieldComponent } from "../fieldTypes";
import { DocKey, ParentDocKey } from "../types";
import { ResolveFieldKey } from "../../FormLayout/types";
import type { TiptapEditor } from "frappe-ui/editor";

const { transport } = vi.hoisted(() => ({
  transport: vi.fn(async () => ({ file_url: "/private/files/a.png", name: "F-1" })),
}));
vi.mock("../../FileUpload/useFileUpload", () => ({ defaultTransport: transport }));

const field = { fieldname: "notes", fieldtype: "Text Editor", label: "Notes" };

let app: App | undefined;
let host: HTMLElement | undefined;

beforeEach(() => transport.mockClear());

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function mount(
  modelValue: string | null,
  options: { readOnly?: boolean; doc?: Record<string, any>; parentDoc?: Record<string, any> } = {}
) {
  const value = ref(modelValue);
  const onInput = vi.fn((next: string) => (value.value = next));
  const onChange = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TextEditorField, {
        field: { ...field, readOnly: options.readOnly },
        modelValue: value.value,
        "onUpdate:modelValue": onInput,
        onChange,
      }),
  });
  app.provide(DocKey, ref(options.doc ?? {}));
  if (options.parentDoc) app.provide(ParentDocKey, ref(options.parentDoc));
  app.mount(host);
  return { root: host, value, onInput, onChange };
}

// tiptap moves the DOM focus a frame after its focus and blur commands.
const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));

async function editorIn(root: HTMLElement): Promise<TiptapEditor> {
  await vi.waitFor(() => expect(root.querySelector(".ProseMirror")).not.toBeNull(), {
    timeout: 10_000,
  });
  await nextTick();
  return (root.querySelector(".ProseMirror") as any).editor;
}

describe("an editable Text Editor", () => {
  it("writes on every edit and commits once on blur", async () => {
    const { root, onInput, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus("end");
    await frame();
    editor.commands.insertContent(" there");
    editor.commands.insertContent("!");
    expect(onInput.mock.calls.map(([v]) => v)).toEqual([
      "<p>Hello there</p>",
      "<p>Hello there!</p>",
    ]);
    expect(onChange).not.toHaveBeenCalled();
    editor.commands.blur();
    await frame();
    expect(onChange.mock.calls).toEqual([["<p>Hello there!</p>"]]);
  });

  it("keeps the edit open across a click on its own toolbar", async () => {
    const { root, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus("end");
    await frame();
    editor.commands.insertContent(" there");
    const bold = root.querySelector<HTMLButtonElement>("[data-slot='fixed-menu'] button[aria-label='Bold']")!;
    bold.focus();
    editor.chain().selectAll().toggleBold().run();
    editor.commands.focus();
    await frame();
    expect(onChange).not.toHaveBeenCalled();
    editor.commands.blur();
    await frame();
    expect(onChange.mock.calls).toEqual([["<p><strong>Hello there</strong></p>"]]);
  });

  it("commits when focus leaves the field from its toolbar", async () => {
    const { root, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus("end");
    await frame();
    editor.commands.insertContent(" there");
    // happy-dom does not move focus onto the toolbar's buttons, so the moves are dispatched.
    const button = root.querySelector<HTMLButtonElement>("[data-slot='fixed-menu'] button")!;
    const move = (from: Element, to: Element) => {
      from.dispatchEvent(new FocusEvent("blur", { relatedTarget: to }));
      from.dispatchEvent(new FocusEvent("focusout", { relatedTarget: to, bubbles: true }));
    };
    move(editor.view.dom, button);
    expect(onChange).not.toHaveBeenCalled();
    move(button, document.body);
    expect(onChange.mock.calls).toEqual([["<p>Hello there</p>"]]);
  });

  it("commits nothing for a value its host set while it had focus", async () => {
    const { root, value, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus("end");
    await frame();
    value.value = "<p>Saved elsewhere</p>";
    await nextTick();
    editor.commands.blur();
    await frame();
    expect(editor.getHTML()).toBe("<p>Saved elsewhere</p>");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("commits nothing on a blur with no change", async () => {
    const { root, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus("end");
    await frame();
    editor.commands.blur();
    await frame();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("commits at once an edit made while it has no focus", async () => {
    const { root, onChange } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.insertContentAt(editor.state.doc.content.size, '<p><img src="/files/a.png"></p>');
    expect(onChange).toHaveBeenCalledOnce();
    expect(onChange.mock.calls[0][0]).toContain('src="/files/a.png"');
  });

  it("stores an empty string once cleared", async () => {
    const { root, value } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    editor.commands.focus();
    editor.commands.clearContent(true);
    await nextTick();
    expect(value.value).toBe("");
  });

  it("stores an image-only body", async () => {
    const { root, value } = mount("");
    const editor = await editorIn(root);
    editor.commands.focus();
    editor.commands.setContent('<img src="/files/a.png">', { emitUpdate: true });
    await nextTick();
    expect(value.value).toContain('src="/files/a.png"');
  });

  it("never writes back a desk v1 value it only loaded", async () => {
    const v1 =
      '<div class="ql-editor read-mode"><p class="ql-indent-1"><span style="font-size: 18px">Big</span></p></div>';
    const { root, onInput, onChange } = mount(v1);
    await editorIn(root);
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(onInput).not.toHaveBeenCalled();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("drops a script attribute from a stored value", async () => {
    const { root, onInput } = mount('<p>Hi</p><img src="x" onerror="window.__textEditorRan()">');
    await editorIn(root);
    const image = root.querySelector(".ProseMirror img");
    expect(image?.getAttribute("src")).toBe("x");
    expect(image?.hasAttribute("onerror")).toBe(false);
    expect(onInput).not.toHaveBeenCalled();
  });

  it("shows a value its host sets", async () => {
    const { root, value } = mount("<p>Hello</p>");
    const editor = await editorIn(root);
    value.value = "<p>Replaced</p>";
    await nextTick();
    await nextTick();
    expect(editor.getHTML()).toBe("<p>Replaced</p>");
  });
});

describe("a Text Editor's image upload", () => {
  const file = new File(["png"], "a.png", { type: "image/png" });

  async function uploadIn(options: Parameters<typeof mount>[1]) {
    const { root } = mount("", options);
    const editor = await editorIn(root);
    const upload = (editor.storage as any).upload.uploadFunction;
    return upload(file);
  }

  it("attaches to a saved record, with no field", async () => {
    await uploadIn({ doc: { doctype: "Note", name: "N-1" } });
    expect(transport.mock.calls[0][1]).toEqual({
      isPrivate: true,
      attachTo: { doctype: "Note", docname: "N-1" },
    });
  });

  it("attaches a row's image to the parent record", async () => {
    await uploadIn({
      doc: { doctype: "Note Row", name: "row-1" },
      parentDoc: { doctype: "Note", name: "N-1" },
    });
    expect(transport.mock.calls[0][1].attachTo).toEqual({ doctype: "Note", docname: "N-1" });
  });

  it("uploads a detached private file for a new record", async () => {
    const media = await uploadIn({ doc: { title: "Unsaved" } });
    expect(transport.mock.calls[0][1]).toEqual({ isPrivate: true, attachTo: undefined });
    expect(media.file_url).toBe("/private/files/a.png");
  });
});

describe("a read-only Text Editor", () => {
  it("draws the value with no editor", async () => {
    const { root } = mount("<p>Hello <b>there</b></p>", { readOnly: true });
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(root.querySelector(".ProseMirror")).toBeNull();
    expect(root.querySelector('[data-slot="text-editor-value"] b')?.textContent).toBe("there");
  });
});

describe("a Text Editor grid cell", () => {
  it("shows its text on one line, with no editor", () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    const table = { fieldname: "items", fieldtype: "Table", childFields: [{ ...field }] };
    const notes = "<h2>Plan</h2><p>Fish &amp; chips</p>";
    app = createApp({
      render: () => h(TableField, { field: table, modelValue: [{ name: "r1", notes }] }),
    });
    app.provide(ResolveFieldKey, getFieldComponent);
    app.mount(host);
    const cell = host.querySelector<HTMLElement>('[data-fieldname="notes"]')!;
    expect(cell.textContent?.trim()).toBe("Plan Fish & chips");
    expect(cell.querySelector(".ProseMirror")).toBeNull();
  });
});
