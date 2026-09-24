// The strip's skeleton: drawn only while the surfaced fields wait on the first meta read.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, reactive } from "vue";
import type { App } from "vue";
import type { RawMetaField } from "../../FormLayout/types";
import type { FilterField } from "../../Filter/types";

const state = vi.hoisted(() => ({ meta: null as any, loading: null as any }));
vi.mock("../../../composables/useDoctypeMeta", async () => {
  const { ref } = await import("vue");
  state.meta = ref(null);
  state.loading = ref(false);
  return { useDoctypeMeta: () => ({ meta: state.meta, loading: state.loading }) };
});

// The inputs face is its own component; this reads which fields it was handed.
vi.mock("../QuickFilterInputs.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    default: defineComponent({
      props: { fields: Array },
      setup: (props) => () =>
        h(
          "div",
          { "data-inputs": "" },
          (props.fields as FilterField[]).map((f) => h("input", { name: f.fieldname })),
        ),
    }),
  };
});

// The customize face pulls in vuedraggable, which the frontend workspace does not install.
vi.mock("../QuickFilterCustomize.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return { default: defineComponent({ setup: () => () => h("div") }) };
});

import QuickFilter from "../QuickFilter.vue";

const STATUS: RawMetaField = {
  fieldname: "status",
  fieldtype: "Select",
  label: "Status",
  in_standard_filter: 1,
};

const apps: App[] = [];

beforeEach(() => {
  state.meta.value = null;
  state.loading.value = false;
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

async function mount(fields?: FilterField[]) {
  const props = reactive({ doctype: "Test DT", fields });
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h(QuickFilter, { ...props }) }));
  app.mount(root);
  apps.push(app);
  await nextTick();
  return {
    bars: () => root.querySelectorAll("[data-quick-filter-skeleton] .fui-skeleton").length,
    inputs: () => [...root.querySelectorAll("[data-inputs] input")].map((i) => i.getAttribute("name")),
  };
}

describe("QuickFilter skeleton", () => {
  it("draws three bars while the first meta read is in flight, then the inputs", async () => {
    state.loading.value = true;
    const strip = await mount();
    expect(strip.bars()).toBe(3);
    expect(strip.inputs()).toEqual([]);

    state.meta.value = { name: "Test DT", fields: [STATUS] };
    state.loading.value = false;
    await nextTick();
    expect(strip.bars()).toBe(0);
    expect(strip.inputs()).toEqual(["name", "status"]);
  });

  it("draws no bars for a loaded doctype with no standard filters", async () => {
    state.meta.value = { name: "Test DT", fields: [] };
    const strip = await mount();
    expect(strip.bars()).toBe(0);
    expect(strip.inputs()).toEqual(["name"]);
  });

  it("draws no bars when the host binds its own fields before the meta arrives", async () => {
    state.loading.value = true;
    const strip = await mount([
      { label: "Status", value: "status", fieldname: "status", fieldtype: "Select" },
    ]);
    expect(strip.bars()).toBe(0);
    expect(strip.inputs()).toEqual(["status"]);
  });

  it("falls back to the Name input when the meta read failed", async () => {
    const strip = await mount();
    expect(strip.bars()).toBe(0);
    expect(strip.inputs()).toEqual(["name"]);
  });
});
