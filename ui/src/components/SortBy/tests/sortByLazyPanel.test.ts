// The sort popover loads vuedraggable on its first open and opens only once it is in.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";
import type { Sort } from "../types";

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
          (props.modelValue as Sort[]).map((element, index) => slots.item?.({ element, index })),
        ),
    }),
  };
});

import SortBy from "../SortBy.vue";

const apps: App[] = [];

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

function mount(initial: Sort[]) {
  const model = ref(initial);
  const el = document.createElement("div");
  document.body.appendChild(el);
  const app = createApp({
    render: () =>
      h(SortBy, {
        doctype: "Test DT",
        modelValue: model.value,
        "onUpdate:modelValue": (next: Sort[]) => (model.value = next),
      }),
  });
  app.mount(el);
  apps.push(app);
  return { el, model };
}

async function settle() {
  for (let i = 0; i < 5; i++) {
    await new Promise((resolve) => setTimeout(resolve));
    await nextTick();
  }
}

function openTrigger(el: HTMLElement) {
  [...el.querySelectorAll("button")].find((b) => b.textContent?.includes("Title"))!.click();
}

describe("SortBy panel", () => {
  it("does not load vuedraggable until opened, and opens only once it is in", async () => {
    const { el } = mount([{ fieldname: "title", direction: "asc" }]);
    await settle();
    expect(state.loads).toBe(0);

    openTrigger(el);
    await settle();
    expect(state.loads).toBe(1);
    expect(document.body.textContent).not.toContain("Add Sort");

    state.release();
    await settle();
    expect(document.body.querySelector("[data-draggable] .sort-drag-handle")).not.toBeNull();
    expect(document.body.textContent).toContain("Add Sort");
  });

  it("starts closed again after the last sort is removed", async () => {
    state.release();
    const { el, model } = mount([{ fieldname: "title", direction: "asc" }]);
    openTrigger(el);
    await settle();
    expect(document.body.textContent).toContain("Add Sort");

    model.value = [];
    await settle();
    model.value = [{ fieldname: "status", direction: "asc" }];
    await settle();
    expect(document.body.textContent).not.toContain("Add Sort");
  });
});
