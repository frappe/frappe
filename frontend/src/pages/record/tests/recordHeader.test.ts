// The header's right-hand order: a script's controls, then the `⋯` menu, then Save.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

// Hoisted with the mocks, so each factory can reach it.
const { Plain } = vi.hoisted(() => ({
  Plain: (tag: string) =>
    defineComponent({
      inheritAttrs: false,
      props: { label: String },
      setup: (props, { attrs, slots }) =>
        () => h(tag, { ...attrs, "data-label": props.label }, slots.default?.()),
    }),
}));

vi.mock("frappe-ui", () => ({
  Button: Plain("button"),
  Dropdown: Plain("div"),
  Tooltip: Plain("span"),
}));

vi.mock("vue-router", () => ({
  RouterLink: Plain("a"),
  useRouter: () => ({ push: vi.fn() }),
}));

import RecordHeader from "../RecordHeader.vue";
import type { HeaderProjection } from "@/recordPage";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

const control = (name: string) => ({ kind: "button" as const, item: { name, label: name } });

async function mount(projection: HeaderProjection) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () => h(RecordHeader, { projection, dirty: false, saving: false }),
    }),
  );
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

const rightHand = (root: HTMLElement) =>
  [...root.querySelectorAll<HTMLElement>("[data-label]")]
    .map((el) => el.dataset.label)
    .filter((label) => label !== "crumb");

describe("the right-hand order", () => {
  it("draws the menu at Save's left, whatever the projection's order", async () => {
    const root = await mount({
      left: [],
      controls: [control("archive"), control("save"), control("export")],
      bands: [{ group: "actions", items: [{ item: { name: "delete", label: "Delete" } }] }],
    });
    expect(rightHand(root)).toEqual(["archive", "export", "More actions", "save"]);
  });

  it("draws no menu without a band, and no Save once a script hid it", async () => {
    const root = await mount({ left: [], controls: [control("export")], bands: [] });
    expect(rightHand(root)).toEqual(["export"]);
  });
});
