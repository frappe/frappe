// The comment card: a saved comment draws as HTML, and the editor mounts only to edit.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import CommentItem from "../CommentItem.vue";
import type { CommentActivity } from "../types";

const comment = {
  type: "comment",
  key: "c-1",
  timestamp: "2026-10-29 10:00:00",
  author: { name: "jane@example.com", fullname: "Jane" },
  data: { content: "<p>Saved <strong>text</strong></p>", attachments: [] },
} as unknown as CommentActivity;

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
});

function mount() {
  const editable = ref(false);
  const onSave = vi.fn();
  const onDiscard = vi.fn();
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () => h(CommentItem, { comment, editable: editable.value, onSave, onDiscard }),
  });
  app.mount(host);
  return { root: host, editable, onSave, onDiscard };
}

function button(root: HTMLElement, label: string) {
  return [...root.querySelectorAll("button")].find((b) => b.textContent?.trim() === label)!;
}

describe("CommentItem", () => {
  it("draws a saved comment without the editor", () => {
    const { root } = mount();
    expect(root.querySelector(".rich-text-view strong")!.textContent).toBe("text");
    expect(root.querySelector(".ProseMirror")).toBeNull();
  });

  it("mounts the editor to edit and saves what was written", async () => {
    const { root, editable, onSave, onDiscard } = mount();
    editable.value = true;
    await vi.waitFor(() => expect(root.querySelector(".ProseMirror")).not.toBeNull(), {
      timeout: 10_000,
    });
    await nextTick();
    const editor = (root.querySelector(".ProseMirror") as any).editor;
    editor.commands.insertContentAt(editor.state.doc.content.size - 1, " more");
    button(root, "Save").click();
    expect(onSave).toHaveBeenCalledWith("<p>Saved <strong>text more</strong></p>");

    button(root, "Discard").click();
    expect(onDiscard).toHaveBeenCalled();
    editable.value = false;
    await nextTick();
    expect(root.querySelector(".ProseMirror")).toBeNull();
    expect(root.querySelector(".rich-text-view")!.textContent).toBe("Saved text");
  });
});
