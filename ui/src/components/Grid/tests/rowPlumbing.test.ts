import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import Grid from "../Grid.vue";
import { ROW_ID } from "../../Fields/rowIdentity";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(options: { newRow?: () => Record<string, any>; cell?: boolean } = {}) {
  const rows = ref<Record<string, any>[]>([]);
  const events: { name: string; payload: any }[] = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(Grid, {
        columns: [{ fieldname: "qty" }],
        modelValue: rows.value,
        newRow: options.newRow,
        "onUpdate:modelValue": (next: any) => (rows.value = next),
        onAdd: (payload: any) => events.push({ name: "add", payload }),
        onRemove: (payload: any) => events.push({ name: "remove", payload }),
        onCommit: (payload: any) => events.push({ name: "commit", payload }),
      },
      options.cell
        ? {
            cell: ({ commit }: any) =>
              h("button", { "data-commit": "", onClick: () => commit(9) }),
          }
        : undefined),
  });
  app.mount(host);
  return { rows, events };
}

function addRow(host: HTMLElement) {
  const button = [...host.querySelectorAll("button")].find((b) =>
    b.textContent?.includes("Add Row")
  )!;
  button.dispatchEvent(new Event("click"));
}

describe("Grid row plumbing", () => {
  it("mints an id on a new row and announces it", async () => {
    const { rows, events } = render();
    addRow(host!);
    expect(rows.value).toHaveLength(1);
    expect(rows.value[0][ROW_ID]).toBeTruthy();
    expect(events).toEqual([{ name: "add", payload: { row: rows.value[0] } }]);
  });

  it("seeds the new row from `newRow`", () => {
    const { rows } = render({ newRow: () => ({ qty: 1 }) });
    addRow(host!);
    expect(rows.value[0].qty).toBe(1);
    expect(rows.value[0][ROW_ID]).toBeTruthy();
  });

  it("names the row and the column a committed cell belongs to", async () => {
    const { rows, events } = render({ cell: true });
    addRow(host!);
    await nextTick();
    host!.querySelector<HTMLElement>("[data-commit]")!.dispatchEvent(new Event("click"));
    expect(events.at(-1)).toEqual({
      name: "commit",
      payload: { row: rows.value[0], column: { fieldname: "qty" } },
    });
    expect(rows.value[0].qty).toBe(9);
  });
});
