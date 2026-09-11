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

const band = { group: "actions", items: [{ item: { name: "delete", label: "Delete" } }] };

describe("the right-hand order", () => {
  it("slots the menu in at Save's left and keeps the projection's order around it", async () => {
    const root = await mount({
      left: [],
      controls: [control("archive"), control("save"), control("export")],
      bands: [band],
    });
    expect(rightHand(root)).toEqual(["archive", "More actions", "save", "export"]);
  });

  it("draws the menu last once a script hid Save, and none without a band", async () => {
    const hidden = await mount({ left: [], controls: [control("export")], bands: [band] });
    expect(rightHand(hidden)).toEqual(["export", "More actions"]);

    const bare = await mount({ left: [], controls: [control("save")], bands: [] });
    expect(rightHand(bare)).toEqual(["save"]);
  });
});
