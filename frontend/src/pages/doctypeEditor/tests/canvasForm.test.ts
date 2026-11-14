import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, ref, type App } from "vue";

vi.mock("../CanvasSection.vue", () => ({ default: { render: () => null } }));
vi.mock("../CanvasTabs.vue", () => ({
  default: { render: () => h("div", { "data-canvas-tabs": "" }) },
}));
vi.mock("vuedraggable", () => ({ default: { render: () => null } }));
vi.mock("@/acts/dispatcher", () => ({ acts: { perform: vi.fn() } }));

import CanvasForm from "../CanvasForm.vue";

let app: App | null = null;
const dom = document.createElement("div");

function mount(
  tabCount: number,
  props: { tabbed?: boolean; editable?: boolean } = {},
) {
  const tabs = Array.from({ length: tabCount }, (_, index) => ({
    name: `tab${index}`,
    sections: [],
  }));
  const canvas = {
    editable: props.editable ?? true,
    tabs: ref(tabs),
    openTab: ref(tabs[0]),
  };
  app = createApp({
    render: () =>
      h(CanvasForm, { canvas: canvas as never, tabbed: props.tabbed ?? true }),
  });
  app.mount(dom);
}
const labels = () =>
  [...dom.querySelectorAll("[data-canvas-add-section] button")].map((one) =>
    one.textContent?.trim(),
  );

afterEach(() => {
  app?.unmount();
  app = null;
});

it("puts Add tab beside Add section on a one-tab form, with no tab strip", () => {
  mount(1);
  expect(labels()).toEqual(["Add section", "Add tab"]);
  expect(dom.querySelector("[data-canvas-tabs]")).toBeNull();
});

it("leaves Add tab to the strip from two tabs up", () => {
  mount(2);
  expect(labels()).toEqual(["Add section"]);
  expect(dom.querySelector("[data-canvas-tabs]")).not.toBeNull();
});

it("offers no Add tab inside a frame", () => {
  mount(1, { tabbed: false });
  expect(labels()).toEqual(["Add section"]);
});
