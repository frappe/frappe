// The column popover loads vuedraggable on its first open and opens only once it is in.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { Column } from "../types";

const state = vi.hoisted(() => {
  let release = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  return { gate, release: () => release(), loads: 0 };
});

vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  const fields = [
    { fieldname: "title", fieldtype: "Data", label: "Title" },
    { fieldname: "status", fieldtype: "Select", label: "Status" },
  ];
  return { useDoctypeMeta: () => ({ meta: ref({ fields }), loading: ref(false) }) };
});

vi.mock("vuedraggable", async () => {
  state.loads++;
  await state.gate;
  const { defineComponent, h } = await import("vue");
  return {
    __esModule: true,
    default: defineComponent({
      props: { modelValue: Array },
      setup: (props, { slots }) => () =>
        h(
          "div",
          { "data-draggable": "" },
          (props.modelValue as Column[]).map((element, index) => slots.item?.({ element, index })),
        ),
    }),
  };
});

import ColumnSettings from "../ColumnSettings.vue";

const apps: App[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

async function settle() {
  for (let i = 0; i < 5; i++) {
    await new Promise((resolve) => setTimeout(resolve));
    await nextTick();
  }
}

describe("ColumnSettings panel", () => {
  it("opens on the row list after the first column is picked", async () => {
    const model = ref<Column[]>([]);
    const el = document.createElement("div");
    document.body.appendChild(el);
    const app = createApp({
      render: () =>
        h(ColumnSettings, {
          doctype: "Test DT",
          modelValue: model.value,
          "onUpdate:modelValue": (next: Column[]) => (model.value = next),
        }),
    });
    app.mount(el);
    apps.push(app);
    await settle();
    expect(state.loads).toBe(0);

    el.querySelector<HTMLButtonElement>("button[aria-label=Columns]")!.click();
    await settle();
    [...document.body.querySelectorAll<HTMLElement>("[role=option]")]
      .find((option) => option.textContent?.includes("Status"))!
      .click();
    await settle();

    expect(model.value.map((column) => column.fieldname)).toEqual(["status"]);
    expect(state.loads).toBe(1);
    expect(document.body.querySelector("[data-draggable]")).toBeNull();

    state.release();
    await settle();
    expect(document.body.querySelector("[data-draggable] .column-drag-handle")).not.toBeNull();
  });
});
