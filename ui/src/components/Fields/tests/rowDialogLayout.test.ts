// The row dialog draws the layout its row chooses (`rowLayout`), and a new row still
// takes its defaults from the child's full form (`childLayout`).
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";

// Passthroughs for frappe-ui's Dialog and reka's Tabs, as in `rowEditDialog.test.ts`.
vi.mock("frappe-ui", async (importOriginal) => {
  const real = (await importOriginal()) as Record<string, unknown>;
  return {
    ...real,
    ...(await import("../../Grid/tests/menuStubs")),
    Dialog: defineComponent({
      props: { open: { type: Boolean, default: false } },
      emits: ["update:open"],
      setup: (props, { slots }) => () =>
        props.open ? h("div", { "data-dialog": "" }, slots.default?.()) : null,
    }),
    Tabs: defineComponent({
      props: { tabs: { type: Array, default: () => [] } },
      emits: ["update:modelValue"],
      setup: (props, { slots }) => () =>
        h(
          "div",
          (props.tabs as any[]).map((tab) => slots["tab-panel"]?.({ tab }))
        ),
    }),
  };
});

vi.mock("../../FormLayout/useFieldTypes", () => ({
  useFieldTypes: () => ({ resolve: () => StubField }),
}));

import TableField from "../TableField.vue";
import { ResolveFieldKey } from "../../FormLayout/types";
import type { FormLayoutSchema } from "../../FormLayout/types";

const StubField = defineComponent({
  props: { field: { type: Object, required: true }, modelValue: null, error: null },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    return () =>
      h("input", {
        "data-fieldname": props.field.fieldname,
        "data-error": props.error,
        value: props.modelValue ?? "",
        onInput: (event: any) => emit("update:modelValue", event.target.value),
        onChange: (event: any) => emit("change", event.target.value),
      });
  },
});

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

const qty = { fieldname: "qty", fieldtype: "Data", label: "Qty" };
const kind = { fieldname: "kind", fieldtype: "Data", label: "Kind" };
const unit = { fieldname: "unit", fieldtype: "Data", label: "Unit", default: "Nos" };

function layoutOf(...fields: Record<string, any>[]): FormLayoutSchema {
  return [{ name: "first_tab", sections: [{ name: "main", columns: [{ fields }] }] }];
}

/** A service row's dialog has no Qty; every other row's has no Kind; neither places Unit. */
const rowLayout = (row: Record<string, any>) =>
  row.kind === "Service" ? layoutOf(kind) : layoutOf(qty);

function render(initial: Record<string, any>[]) {
  const rows = ref(initial);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TableField, {
        field: {
          fieldname: "products",
          fieldtype: "Table",
          label: "Products",
          childFields: [qty],
          childLayout: layoutOf(qty, kind, unit),
          rowLayout,
        },
        modelValue: rows.value,
        "onUpdate:modelValue": (value: any) => (rows.value = value),
      }),
  });
  app.provide(ResolveFieldKey, () => StubField);
  app.mount(host);
  return rows;
}

function openRow(index: number) {
  const items = host!.querySelectorAll<HTMLElement>('.sticky.right-0 [data-menu-item="Edit"]');
  items[index].dispatchEvent(new Event("click"));
  return flush();
}

async function flush(): Promise<void> {
  // The dialog's `FormLayout` is a `defineAsyncComponent`, which renders a comment
  // placeholder until its dynamic import settles — several turns of the loop.
  await import("../../FormLayout/FormLayout.vue");
  for (let i = 0; i < 10; i++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await nextTick();
  }
}

function dialogFields(): string[] {
  return [...host!.querySelectorAll<HTMLInputElement>("[data-dialog] input")].map(
    (input) => input.dataset.fieldname!
  );
}

describe("the row dialog's layout", () => {
  it("draws the layout the opened row chooses", async () => {
    render([
      { name: "a", kind: "Service" },
      { name: "b", kind: "Goods" },
    ]);
    await openRow(0);
    expect(dialogFields()).toEqual(["kind"]);
  });

  it("draws another row's own layout", async () => {
    render([
      { name: "a", kind: "Service" },
      { name: "b", kind: "Goods" },
    ]);
    await openRow(1);
    expect(dialogFields()).toEqual(["qty"]);
  });

  it("gives a new row the default of a child field no row layout places", async () => {
    const rows = render([]);
    const add = [...host!.querySelectorAll("button")].find(
      (button) => button.textContent?.trim() === "Add Row"
    )!;
    add.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await flush();
    expect(rows.value).toHaveLength(1);
    expect(rows.value[0].unit).toBe("Nos");
  });
});
