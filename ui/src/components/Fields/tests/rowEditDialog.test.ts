// The row-edit dialog writes THROUGH to the row (wayfinder ticket 58 §B): it
// holds an address rather than a reference, so it survives a reorder, closes
// when its row stops resolving, and never reassigns the table's array.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";
import type { App } from "vue";

// Dialog chrome is frappe-ui's; a passthrough keeps the test on TableField's
// behaviour rather than reka-ui's transitions. Everything else stays real
// (`Grid` composes frappe-ui atoms).
vi.mock("frappe-ui", async (importOriginal) => {
  const real = (await importOriginal()) as Record<string, unknown>;
  return {
    ...real,
    Dialog: defineComponent({
      props: { open: { type: Boolean, default: false } },
      emits: ["update:open"],
      setup: (props, { slots }) => () =>
        props.open ? h("div", { "data-dialog": "" }, slots.default?.()) : null,
    }),
    // `FormLayout` renders its sections through reka-ui's `Tabs`, which paints
    // nothing here (the reason the FormLayout tests stop at `FormLayoutColumn`).
    // A passthrough renders every panel, so the real FormLayout runs.
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

// FormLayout resolves fieldtypes through its own registry, so the dialog's
// fields are stubbed there.
vi.mock("../../FormLayout/useFieldTypes", () => ({
  useFieldTypes: () => ({ resolve: () => StubField }),
}));

import TableField from "../TableField.vue";
import { ResolveFieldKey } from "../../FormLayout/types";
import { CommitKey } from "../types";
import { ROW_ID } from "../rowIdentity";
import type { CommitChannel, RowAddress } from "../types";

// Stands in for every fieldtype, in the cell and in the dialog alike.
const StubField = defineComponent({
  props: { field: { type: Object, required: true }, modelValue: null },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    return () =>
      h("input", {
        "data-fieldname": props.field.fieldname,
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

const childFields = [
  { fieldname: "qty", fieldtype: "Data", label: "Qty" },
  { fieldname: "notes", fieldtype: "Data", label: "Notes" },
];

function render(
  initial: Record<string, any>[],
  onCommit?: (fieldname: string, value: any) => void
) {
  const rows = ref(initial);
  const emitted: { name: string; value: any }[] = [];
  const committed: { fieldname: string; value: any; row?: RowAddress }[] = [];
  const channel: CommitChannel = {
    pending: (fieldname, value, row) => committed.push({ fieldname, value, row }),
    commit: (fieldname, value, row) => {
      committed.push({ fieldname, value, row });
      onCommit?.(fieldname, value);
    },
    rowChanged: () => {},
  };
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(TableField, {
        field: { fieldname: "products", fieldtype: "Table", label: "Products", childFields },
        modelValue: rows.value,
        "onUpdate:modelValue": (v: any) => emitted.push({ name: "update:modelValue", value: v }),
        onChange: (v: any) => emitted.push({ name: "change", value: v }),
      }),
  });
  app.provide(ResolveFieldKey, () => StubField);
  app.provide(CommitKey, channel);
  app.mount(host);
  return { rows, emitted, committed };
}

/** The per-row edit button lives in the frozen right-hand column. */
function openRow(index: number) {
  const buttons = host!.querySelectorAll<HTMLElement>(".sticky.right-0 button");
  buttons[index].dispatchEvent(new Event("click"));
  // The dialog's FormLayout is an async component (module-cycle break), so the
  // dynamic import has to settle before its fields are in the DOM.
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

function dialog(): HTMLElement | null {
  return host!.querySelector("[data-dialog]");
}

function typeInDialog(fieldname: string, value: string) {
  const input = dialog()!.querySelector<HTMLInputElement>(`input[data-fieldname="${fieldname}"]`)!;
  input.value = value;
  input.dispatchEvent(new Event("input"));
}

function commitInDialog(fieldname: string) {
  const input = dialog()!.querySelector<HTMLInputElement>(`input[data-fieldname="${fieldname}"]`)!;
  input.dispatchEvent(new Event("change"));
}

describe("row-edit dialog", () => {
  it("writes through to the row, without reassigning the table's array", async () => {
    const row = { name: "r1", qty: "1", notes: "" };
    const { rows, emitted } = render([row]);
    await openRow(0);
    expect(dialog()).not.toBeNull();

    typeInDialog("qty", "3");
    expect(row.qty).toBe("3");
    expect(emitted.filter((e) => e.name === "update:modelValue")).toEqual([]);
    expect(emitted.filter((e) => e.name === "change")).toEqual([]);
  });

  it("addresses its commits to the open row", async () => {
    const { committed } = render([{ name: "r1", qty: "1" }, { name: "r2", qty: "2" }]);
    await openRow(1);
    typeInDialog("qty", "9");
    expect(committed.at(-1)).toEqual({
      fieldname: "qty",
      value: "9",
      row: { parentfield: "products", key: "name:r2" },
    });
  });

  it("follows its row through a reorder underneath it", async () => {
    const first = { name: "r1", qty: "1" };
    const second = { name: "r2", qty: "2" };
    const { rows } = render([first, second]);
    await openRow(0);

    rows.value = [second, first];
    await nextTick();
    expect(dialog()).not.toBeNull();
    typeInDialog("qty", "7");
    expect(first.qty).toBe("7");
    expect(second.qty).toBe("2");
  });

  it("re-resolves a saved row across the repaint that replaces every row object", async () => {
    const { rows } = render([{ name: "r1", qty: "1" }]);
    await openRow(0);

    // `paintSaved`: fresh objects, same names.
    rows.value = [{ name: "r1", qty: "1" }];
    await nextTick();
    expect(dialog()).not.toBeNull();
    typeInDialog("qty", "5");
    expect(rows.value[0].qty).toBe("5");
  });

  it("keeps what a handler writes into the row on commit", async () => {
    // What the clone actually cost: the write-back overwrote the row a tick
    // after a handler had written to it, so the next handler read the old value.
    const row: Record<string, any> = { name: "r1", qty: "1", notes: "" };
    const { rows } = render([row], (fieldname) => {
      if (fieldname === "qty") row.notes = `handler saw ${row.qty}`;
    });
    await openRow(0);
    typeInDialog("qty", "4");
    commitInDialog("qty");
    expect(row.notes).toBe("handler saw 4");

    // A write-back would land here, one tick later.
    await flush();
    expect(row.notes).toBe("handler saw 4");
    expect(rows.value[0].notes).toBe("handler saw 4");
  });

  it("stays closed when a row answering to its key comes back", async () => {
    // A save conflict repaints the server's rows and then re-applies the
    // reader's, so a row that vanished can return moments later. The dialog must
    // not re-open by itself on top of the conflict dialog.
    const { rows } = render([{ name: "r1", qty: "1" }, { name: "r2", qty: "2" }]);
    await openRow(0);
    const [first, ...rest] = rows.value;
    rows.value = rest;
    await nextTick();
    expect(dialog()).toBeNull();

    rows.value = [first, ...rest];
    await nextTick();
    expect(dialog()).toBeNull();
  });

  it("edits the row that was clicked when two rows answer to one key", async () => {
    // `{ ...products[0] }` in a script copies the row's `name`, so two rows can
    // share an address; a bare first-match would open on the wrong one.
    const { rows } = render([
      { name: "dup", qty: "A" },
      { name: "dup", qty: "B" },
    ]);
    await openRow(1);
    typeInDialog("qty", "Z");
    expect(rows.value[1].qty).toBe("Z");
    expect(rows.value[0].qty).toBe("A");
  });

  it("closes when its row is removed", async () => {
    const { rows } = render([{ name: "r1", qty: "1" }, { name: "r2", qty: "2" }]);
    await openRow(0);
    rows.value = rows.value.slice(1);
    await nextTick();
    expect(dialog()).toBeNull();
  });

  it("closes when a row added this session is detached by a save", async () => {
    const added = { [ROW_ID]: "row-99", qty: "1" };
    const { rows } = render([added]);
    await openRow(0);
    expect(dialog()).not.toBeNull();

    // The server strips `__row_id` and names the row: neither identifier survives.
    rows.value = [{ name: "r1", qty: "1" }];
    await nextTick();
    expect(dialog()).toBeNull();
  });
});
