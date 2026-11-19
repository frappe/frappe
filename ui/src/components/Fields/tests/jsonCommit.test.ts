// What a JSON field emits when it is edited and when it loses focus.
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import CodeEditorField from "../CodeEditorField.vue";

let app: App | null = null;
let host: HTMLElement;

afterEach(() => {
  app?.unmount();
  app = null;
  host.remove();
});

async function edit(fieldtype: string, from: string, to: string, blur = true) {
  const committed: unknown[] = [];
  const live: unknown[] = [];
  const field = { fieldname: "payload", fieldtype, label: "Payload", placeholder: "" };
  host = document.body.appendChild(document.createElement("div"));
  app = createApp({
    render: () =>
      h(CodeEditorField, {
        field,
        modelValue: from,
        onChange: (v: unknown) => committed.push(v),
        "onUpdate:modelValue": (v: unknown) => live.push(v),
      }),
  });
  app.mount(host);
  await nextTick();
  const view = EditorView.findFromDOM(host.querySelector(".cm-editor") as HTMLElement)!;
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: to } });
  if (blur) view.contentDOM.dispatchEvent(new FocusEvent("blur"));
  await nextTick();
  return { committed, live };
}

async function commit(fieldtype: string, from: string, to: string) {
  return (await edit(fieldtype, from, to)).committed;
}

describe("JSON field commit", () => {
  it("commits null when the field is cleared", async () => {
    expect(await commit("JSON", '{"a": 1}', "  ")).toEqual([null]);
  });

  it("holds null while the cleared field still has focus", async () => {
    expect((await edit("JSON", '{"a": 1}', "", false)).live).toEqual([null]);
  });

  it("pretty-prints valid JSON", async () => {
    expect(await commit("JSON", "", '{"a":1}')).toEqual(['{\n  "a": 1\n}']);
  });

  it("keeps an empty Code field as an empty string", async () => {
    expect(await commit("Code", "x = 1", "")).toEqual([""]);
  });
});
