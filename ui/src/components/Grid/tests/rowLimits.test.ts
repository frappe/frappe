import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import Grid from "../Grid.vue";

let app: App | undefined;
let host: HTMLElement | undefined;

afterEach(() => {
  app?.unmount();
  host?.remove();
  app = undefined;
  host = undefined;
});

function render(limits: { cannotAddRows?: boolean; cannotDeleteRows?: boolean }) {
  const rows = ref<Record<string, any>[]>([
    { name: "a", qty: 1 },
    { name: "b", qty: 2 },
  ]);
  host = document.createElement("div");
  document.body.appendChild(host);
  app = createApp({
    render: () =>
      h(Grid, {
        columns: [{ fieldname: "qty" }],
        modelValue: rows.value,
        "onUpdate:modelValue": (next: any) => (rows.value = next),
        ...limits,
      }),
  });
  app.mount(host);
  return { rows };
}

function button(label: string): HTMLButtonElement | undefined {
  return [...host!.querySelectorAll("button")].find((b) => b.textContent?.includes(label));
}

async function selectAll() {
  host!
    .querySelector<HTMLElement>('[aria-label="Select all"]')!
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
  await nextTick();
}

describe("Grid row limits", () => {
  it("offers Add Row and Delete when neither limit is set", async () => {
    render({});
    await selectAll();
    expect(button("Add Row")).toBeDefined();
    expect(button("Delete (2)")).toBeDefined();
  });

  it("hides Add Row under cannotAddRows, but still deletes a selection", async () => {
    const { rows } = render({ cannotAddRows: true });
    expect(button("Add Row")).toBeUndefined();
    await selectAll();
    button("Delete (2)")!.dispatchEvent(new Event("click"));
    await nextTick();
    expect(rows.value).toEqual([]);
  });

  it("hides Delete for a selection under cannotDeleteRows, but still adds", async () => {
    const { rows } = render({ cannotDeleteRows: true });
    await selectAll();
    expect(button("Delete")).toBeUndefined();
    button("Add Row")!.dispatchEvent(new Event("click"));
    await nextTick();
    expect(rows.value).toHaveLength(3);
  });

  it("keeps rows reorderable under both limits", () => {
    render({ cannotAddRows: true, cannotDeleteRows: true });
    expect(host!.querySelector(".grid-drag-handle")).not.toBeNull();
    expect(button("Add Row")).toBeUndefined();
    expect(button("Delete")).toBeUndefined();
  });
});
