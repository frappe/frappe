// The customize face loads when customizing starts; the inputs stay until it is in.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";
import type { App } from "vue";

const state = vi.hoisted(() => {
  let release = () => {};
  const gate = new Promise<void>((resolve) => (release = resolve));
  return { gate, release: () => release(), loads: 0 };
});

vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  return { useDoctypeMeta: () => ({ meta: ref({ fields: [] }), loading: ref(false) }) };
});

vi.mock("../QuickFilterInputs.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return { default: defineComponent({ setup: () => () => h("div", { "data-inputs": "" }) }) };
});

vi.mock("../QuickFilterCustomize.vue", async () => {
  state.loads++;
  await state.gate;
  const { defineComponent, h } = await import("vue");
  return { default: defineComponent({ setup: () => () => h("div", { "data-customize": "" }) }) };
});

import QuickFilter from "../QuickFilter.vue";

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

describe("QuickFilter customize face", () => {
  it("loads only when customizing starts and keeps the inputs until it is in", async () => {
    const customizing = ref(false);
    const el = document.createElement("div");
    document.body.appendChild(el);
    const app = createApp({
      render: () =>
        h(QuickFilter, {
          doctype: "Test DT",
          customizing: customizing.value,
          "onUpdate:customizing": (next: boolean) => (customizing.value = next),
        }),
    });
    app.mount(el);
    apps.push(app);
    await settle();
    expect(state.loads).toBe(0);
    expect(el.querySelector("[data-inputs]")).not.toBeNull();

    customizing.value = true;
    await settle();
    expect(state.loads).toBe(1);
    expect(el.querySelector("[data-inputs]")).not.toBeNull();
    expect(el.querySelector("[data-customize]")).toBeNull();

    state.release();
    await settle();
    expect(el.querySelector("[data-customize]")).not.toBeNull();
    expect(el.querySelector("[data-inputs]")).toBeNull();
  });
});
