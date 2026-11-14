import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, h, ref, type App } from "vue";

const { selectOn } = vi.hoisted(() => ({ selectOn: vi.fn() }));
vi.mock("../canvasMenu", () => ({ selectOn }));
vi.mock("../CanvasField.vue", () => ({
  default: {
    props: ["fieldname"],
    render() {
      return h("div", { "data-canvas-field": this.fieldname }, this.fieldname);
    },
  },
}));
vi.mock("../RuleMark.vue", () => ({ default: { render: () => null } }));
vi.mock("../canvasDrops", () => ({
  DRAG_OPTIONS: {},
  dropField: vi.fn(),
  dropOnBin: vi.fn(),
  startDrag: vi.fn(),
}));
vi.mock("vuedraggable", () => ({
  default: {
    props: ["modelValue"],
    render() {
      return h(
        "div",
        this.modelValue.map((one: string) =>
          this.$slots.item?.({ element: one }),
        ),
      );
    },
  },
}));

import CanvasColumn from "../CanvasColumn.vue";

let app: App | null = null;
let dom: HTMLElement;

function mount(options: { editable?: boolean; columns?: number } = {}) {
  const section = {
    name: "sec",
    columns: Array.from({ length: options.columns ?? 2 }, (_, index) => ({
      name: `col${index}`,
    })),
  };
  const column = { name: "col0", fields: ["status", "owner"] };
  const canvas = {
    editable: options.editable ?? true,
    selection: ref<unknown>(null),
  };
  app = createApp({
    render: () =>
      h(CanvasColumn, {
        canvas: canvas as never,
        section: section as never,
        column: column as never,
      }),
  });
  app.mount(dom);
  return canvas;
}
const column = () => dom.querySelector("[data-canvas-column]")!;
const ring = () => dom.querySelector("[data-canvas-column-ring]");
const grip = () => dom.querySelector("[data-canvas-column-grip]");

beforeEach(() => {
  dom = document.createElement("div");
  document.body.append(dom);
  selectOn.mockClear();
});
afterEach(() => {
  app?.unmount();
  app = null;
  dom.remove();
});

it("selects the column on a click in its band, not on a field", () => {
  mount();
  dom
    .querySelector("[data-canvas-column-band]")!
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
  expect(selectOn).toHaveBeenCalledWith(expect.anything(), {
    kind: "column",
    section: "sec",
    column: "col0",
  });
  selectOn.mockClear();
  dom
    .querySelector("[data-canvas-field='status']")!
    .dispatchEvent(new MouseEvent("click", { bubbles: true }));
  expect(selectOn).not.toHaveBeenCalled();
});

it("rings the column on hover of its free space, and not over a field", async () => {
  mount();
  expect(ring()).toBeNull();
  dom
    .querySelector("[data-canvas-column-band]")!
    .dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  await Promise.resolve();
  expect(ring()?.className).toContain("ring-outline-gray-3");
  dom
    .querySelector("[data-canvas-field='owner']")!
    .dispatchEvent(new MouseEvent("mouseover", { bubbles: true }));
  await Promise.resolve();
  expect(ring()).toBeNull();
  column().dispatchEvent(new MouseEvent("mouseleave"));
});

it("draws a grip on the ring of a column in a section of two or more", async () => {
  const canvas = mount();
  canvas.selection.value = { kind: "column", section: "sec", column: "col0" };
  await Promise.resolve();
  expect(ring()?.className).toContain("ring-outline-gray-5");
  expect(grip()).not.toBeNull();
});

it("has no grip in a one-column section", async () => {
  const canvas = mount({ columns: 1 });
  canvas.selection.value = { kind: "column", section: "sec", column: "col0" };
  await Promise.resolve();
  expect(ring()).not.toBeNull();
  expect(grip()).toBeNull();
});

it("draws no band, ring or grip when the canvas is read-only", async () => {
  const canvas = mount({ editable: false });
  canvas.selection.value = { kind: "column", section: "sec", column: "col0" };
  await Promise.resolve();
  expect(dom.querySelector("[data-canvas-column-band]")).toBeNull();
  expect(ring()).toBeNull();
  expect(grip()).toBeNull();
});
