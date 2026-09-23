// A disabled editor offers no formatting menu and no editable quote; a sending one no Discard.
// Esc in the body discards unless an editor menu takes it; only Discard and Esc say so.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import ComposerEditor from "../ComposerEditor.vue";

// `dompurify` does not resolve from `ui/`, which has no `node_modules` of its own.
vi.mock("../../../utils/sanitize", () => ({ sanitizeHtml: (html: string) => html }));

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

async function mountEditor(disabled: boolean, submitting = false) {
  const body = ref("<p>Hello</p>");
  const editor = ref<InstanceType<typeof ComposerEditor> | null>(null);
  const uploadFunction = vi.fn(async () => ({ file_url: "/files/a.png" }));
  const onDiscard = vi.fn();
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp({
    render: () =>
      h(ComposerEditor, {
        ref: editor,
        body: body.value,
        "onUpdate:body": (next: string) => (body.value = next),
        quoted: "<p>Earlier</p>",
        uploadFunction,
        disabled,
        submitting,
        onDiscard,
      }),
  });
  app.mount(root);
  apps.push(app);
  for (let i = 0; i < 5; i++) await new Promise((resolve) => setTimeout(resolve));
  await nextTick();
  const tiptap = editor.value!.editor!;
  return { root, body, uploadFunction, onDiscard, editor: editor.value!, tiptap };
}

// ProseMirror claims an Esc by its keyCode, which happy-dom leaves at 0 unless given.
function pressEscape(target: Element) {
  target.dispatchEvent(
    new KeyboardEvent("keydown", { key: "Escape", keyCode: 27, bubbles: true, cancelable: true })
  );
}

function toolbarButtons(root: HTMLElement) {
  return [...root.querySelectorAll<HTMLButtonElement>("[data-slot='fixed-menu'] button")];
}

describe("a disabled composer editor", () => {
  it("draws the formatting toolbar while enabled", async () => {
    const { root } = await mountEditor(false);
    expect(toolbarButtons(root).length).toBeGreaterThan(0);
  });

  it("draws no toolbar, so nothing can format the body or upload", async () => {
    const { root, body, uploadFunction } = await mountEditor(true);
    expect(root.querySelector("[data-slot='fixed-menu']")).toBeNull();
    for (const button of root.querySelectorAll<HTMLButtonElement>("button"))
      if (button.textContent?.trim() !== "Discard") button.click();
    await nextTick();
    expect(body.value).toBe("<p>Hello</p>");
    expect(uploadFunction).not.toHaveBeenCalled();
  });

  it("makes the quoted reply read-only", async () => {
    const quote = async (disabled: boolean) => {
      const { root } = await mountEditor(disabled);
      return root.querySelector("details > div")?.getAttribute("contenteditable");
    };
    expect(await quote(false)).toBe("true");
    expect(await quote(true)).toBe("false");
  });
});

describe("a sending composer editor", () => {
  it("offers no Discard, by button or by Esc, until the send settles", async () => {
    const discard = (root: HTMLElement) =>
      [...root.querySelectorAll("button")].find((one) => one.textContent?.trim() === "Discard");
    expect(discard((await mountEditor(false)).root)).toBeDefined();
    const { root, body } = await mountEditor(false, true);
    expect(discard(root)).toBeUndefined();
    root.querySelector(".composer-body")?.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true })
    );
    await nextTick();
    expect(body.value).toBe("<p>Hello</p>");
  });

  it("keeps the body when Esc lands in it mid-send", async () => {
    const { body, tiptap } = await mountEditor(false, true);
    pressEscape(tiptap.view.dom);
    await nextTick();
    expect(body.value).toBe("<p>Hello</p>");
  });
});

describe("Esc in the body of a composer editor", () => {
  it("discards the draft when no menu is open", async () => {
    const { body, tiptap, onDiscard } = await mountEditor(false);
    pressEscape(tiptap.view.dom);
    await nextTick();
    expect(body.value).toBe("");
    expect(onDiscard).toHaveBeenCalledOnce();
  });

  it("closes an open slash menu and keeps the text", async () => {
    const { body, tiptap } = await mountEditor(false);
    const slashMenu = tiptap.state.plugins.find((one) =>
      (one as unknown as { key: string }).key.startsWith("slashCommandSuggestion")
    )!;
    // Pressed at once: under happy-dom the menu closes by itself a tick later.
    tiptap.chain().focus("end").insertContent(" /").run();
    expect(slashMenu.getState(tiptap.state).active).toBe(true);
    pressEscape(tiptap.view.dom);
    await nextTick();
    expect(slashMenu.getState(tiptap.state).active).toBe(false);
    expect(body.value).toBe("<p>Hello /</p>");
  });
});

describe("the discard event", () => {
  it("fires on the Discard button", async () => {
    const { root, body, onDiscard } = await mountEditor(false);
    const buttons = [...root.querySelectorAll("button")];
    buttons.find((one) => one.textContent?.trim() === "Discard")!.click();
    await nextTick();
    expect([body.value, onDiscard.mock.calls.length]).toEqual(["", 1]);
  });

  it("does not fire on a host's reset", async () => {
    const { body, editor, onDiscard } = await mountEditor(false);
    editor.reset();
    await nextTick();
    expect(body.value).toBe("");
    expect(onDiscard).not.toHaveBeenCalled();
  });

  it("does not fire when select-all and Delete empty the body and the quote", async () => {
    const { root, body, onDiscard } = await mountEditor(false);
    const quote = root.querySelector<HTMLElement>("details > div")!;
    quote.focus();
    const keys = { bubbles: true, cancelable: true };
    quote.dispatchEvent(new KeyboardEvent("keydown", { key: "a", ctrlKey: true, ...keys }));
    quote.dispatchEvent(new KeyboardEvent("keydown", { key: "Delete", ...keys }));
    await nextTick();
    expect(body.value).toBe("");
    expect(root.querySelector("details")).toBeNull();
    expect(onDiscard).not.toHaveBeenCalled();
  });
});
