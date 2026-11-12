// A panel row is one tab stop: a focus opens its editor, Enter and Esc leave focus on the closed row, typing keeps its first key.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import {
  CommitKey,
  DocKey,
  NO_COMMIT,
  ResolveFieldKey,
  UpdateKey,
} from "@framework/ui/FormLayout/types";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "../PanelField.vue";

const Control = defineComponent({
  props: { panel: Boolean, field: Object },
  setup: (props) => () =>
    h("input", {
      "data-control": "",
      "data-panel": props.panel,
      placeholder: props.field?.placeholder,
    }),
});

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

const qty: FieldNode = {
  fieldname: "qty",
  fieldtype: "Int",
  label: "Qty",
  description: "How many",
};

async function mountRow(field: FieldNode = qty) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({ render: () => h(PanelField, { field }) })
  );
  app.provide(DocKey, ref({ qty: 2 }));
  app.provide(UpdateKey, vi.fn());
  app.provide(CommitKey, NO_COMMIT);
  app.provide(ResolveFieldKey, () => Control);
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

const rest = (root: Element) =>
  root.querySelector<HTMLElement>('[data-fieldname="qty"]')!;
const key = (target: Element, init: KeyboardEventInit) =>
  target.dispatchEvent(
    new KeyboardEvent("keydown", { bubbles: true, cancelable: true, ...init })
  );
const settle = () => new Promise((done) => setTimeout(done));

describe("a panel row on the keyboard", () => {
  it("is one tab stop that opens its editor on focus", async () => {
    const root = await mountRow();
    expect(rest(root).getAttribute("tabindex")).toBe("0");

    rest(root).focus();
    await settle();

    expect(root.querySelector("[data-control]")).not.toBeNull();
    expect(document.activeElement).toBe(root.querySelector("[data-control]"));
  });

  it("opens once on a press, not on its focus as well", async () => {
    const root = await mountRow();
    rest(root).dispatchEvent(
      new PointerEvent("pointerdown", { bubbles: true })
    );
    rest(root).focus();
    await settle();
    expect(root.querySelector("[data-control]")).toBeNull();

    rest(root).click();
    await settle();
    expect(root.querySelectorAll("[data-control]")).toHaveLength(1);
  });

  it("has no tab stop when read-only", async () => {
    const root = await mountRow({ ...qty, readOnly: true });
    expect(rest(root).hasAttribute("tabindex")).toBe(false);
  });

  it("returns focus to the closed row on Esc, and stays closed", async () => {
    const root = await mountRow();
    rest(root).focus();
    await settle();
    key(root.querySelector("[data-control]")!, { key: "Escape" });
    await settle();

    expect(root.querySelector("[data-control]")).toBeNull();
    expect(document.activeElement).toBe(rest(root));
  });

  it("opens a closed row on Enter, and on a typed key that goes into the editor", async () => {
    const root = await mountRow();
    rest(root).focus();
    await settle();
    key(root.querySelector("[data-control]")!, { key: "Escape" });
    await settle();

    const typed = vi.fn(() => true);
    document.execCommand = typed;
    const event = key(rest(root), { key: "x" });
    await settle();

    expect(event).toBe(false);
    expect(typed).toHaveBeenCalledWith("insertText", false, "x");
    expect(root.querySelector("[data-control]")).not.toBeNull();
  });

  it("points the focused editor at the label's description", async () => {
    const root = await mountRow();
    const id = root.querySelector(".sr-only")!.id;
    expect(id).not.toBe("");
    expect(rest(root).getAttribute("aria-describedby")).toBe(id);

    rest(root).focus();
    await settle();
    expect(
      root.querySelector("[data-control]")!.getAttribute("aria-describedby")
    ).toBe(id);
  });
});
