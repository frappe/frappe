// The header's two zones: crumb runs and the star left; a script's controls, `⋯`, then Save right.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

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

// Breadcrumbs stays real: the crumb tests read the anchors and separators it draws.
vi.mock("frappe-ui", async (importActual) => ({
  Breadcrumbs: ((await importActual()) as any).Breadcrumbs,
  Button: Plain("button"),
  Dropdown: Plain("div"),
  Tooltip: Plain("span"),
  HoverCard: defineComponent({
    setup: (_, { slots }) => () => h("div", [slots.trigger?.(), slots.default?.()]),
  }),
  // No `data-label`: the order check reads that attribute off every button.
  Avatar: defineComponent({ render: () => h("i") }),
}));

import RecordHeader from "../RecordHeader.vue";
import type { HeaderItem, HeaderProjection } from "@/recordPage";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
  for (const app of mounted.splice(0)) app.unmount();
  document.body.innerHTML = "";
});

const control = (name: string, props: Record<string, any> = {}) => ({
  kind: "button" as const,
  item: { name, label: name },
  source: "test",
  props,
});

// The stub reads no `page`; a component item reads it off its props.
const page = { doctype: "CRM Deal", docname: "D-1" } as any;

type Favourites = { favourites: { id: string; name: string }[]; favourited: boolean };

async function mount(
  projection: HeaderProjection,
  favourites: Favourites = { favourites: [], favourited: false },
  onRun: (item: any) => void = () => {},
  state: { dirty: boolean; saving: boolean } = { dirty: false, saving: false },
) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () => h(RecordHeader, { projection, page, ...state, ...favourites, onRun }),
    }),
  );
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:path(.*)*", component: { render: () => null } }],
  });
  app.use(router);
  await router.isReady();
  app.mount(root);
  mounted.push(app);
  await nextTick();
  return root;
}

const rightHand = (root: HTMLElement) =>
  [...root.querySelectorAll<HTMLElement>("[data-label]")].map((el) => el.dataset.label);

const band = { group: "actions", items: [{ item: { name: "delete", label: "Delete" } }] };

const crumb = (name: string, item: Partial<HeaderItem> = {}) => ({
  kind: "crumb" as const,
  item: { name, label: name, ...item },
});

const crumbRoots = (root: HTMLElement) => [...root.querySelectorAll<HTMLElement>("[data-crumbs]")];

const crumbText = (run: HTMLElement) =>
  [...run.querySelectorAll<HTMLElement>("a, button")].map((el) => el.textContent?.trim());

describe("the crumbs", () => {
  it("draws a run of crumbs as one Breadcrumbs, linked, run or current", async () => {
    const ran: string[] = [];
    const root = await mount(
      {
        left: [
          crumb("Deals", { href: "/deals" }),
          crumb("Open", { run: () => {} }),
          crumb("Acme"),
        ],
        controls: [],
        bands: [],
      },
      undefined,
      (item) => ran.push(item.name),
    );
    const [run, ...rest] = crumbRoots(root);
    expect(rest).toEqual([]);
    expect(crumbText(run)).toEqual(["Deals", "Open", "Acme"]);
    expect(run.textContent?.replace(/\s+/g, " ").trim()).toBe("Deals / Open / Acme");

    const link = run.querySelector<HTMLAnchorElement>("a")!;
    expect(link.getAttribute("href")).toBe("/deals");
    expect(link.textContent?.trim()).toBe("Deals");

    run.querySelector<HTMLButtonElement>("button")!.click();
    expect(ran).toEqual(["Open"]);
  });

  it("splits the run around a control that sits between two crumbs", async () => {
    const root = await mount({
      left: [crumb("Deals"), control("favourite"), crumb("Acme")],
      controls: [],
      bands: [],
    });
    const runs = crumbRoots(root);
    expect(runs.map(crumbText)).toEqual([["Deals"], ["Acme"]]);
    expect(root.querySelector("nav")!.textContent).not.toContain("/");
    const order = [...root.querySelector("nav")!.children].map((el) =>
      el.querySelector("[data-favourite]") ? "star" : el.textContent?.trim(),
    );
    expect(order).toEqual(["Deals", "star", "Acme"]);
  });
});

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

describe("the favourite built-in", () => {
  it("draws the star in the left zone, pressed when the reader favourited", async () => {
    const root = await mount(
      { left: [control("favourite")], controls: [control("save")], bands: [] },
      { favourites: [{ id: "me", name: "You" }], favourited: true },
    );
    const star = root.querySelector<HTMLElement>("[data-favourite]")!;
    expect(star.getAttribute("aria-pressed")).toBe("true");
    expect(star.dataset.label).toBe("Remove from favourites");
    expect(rightHand(root)).toEqual(["Remove from favourites", "save"]);
    expect(root.querySelector("[data-favourites]")?.textContent).toContain("You");
  });

  it("lists nobody without a favourite, and runs the item on click", async () => {
    const ran: string[] = [];
    const root = await mount(
      { left: [], controls: [control("favourite")], bands: [] },
      { favourites: [], favourited: false },
      (item) => ran.push(item.name),
    );
    expect(root.querySelector("[data-favourites]")).toBeNull();
    root.querySelector<HTMLElement>("[data-favourite]")!.click();
    expect(ran).toEqual(["favourite"]);
  });
});

// What the zone hands a component: its wrapper, and `{ ...props, page }`.
const Stamp = defineComponent({
  props: { page: Object, size: String },
  setup: (props) => () =>
    h("span", { "data-stamp": props.size, "data-doc": (props.page as any)?.docname }),
});

const component = (name: string, props: Record<string, any> = {}) => ({
  kind: "component" as const,
  item: { name, label: name, component: Stamp },
  source: "test",
  props,
});

describe("a component in a zone", () => {
  it("grows on the left and receives its props with page", async () => {
    const root = await mount({
      left: [crumb("doctype"), component("stage", { size: "sm" })],
      controls: [],
      bands: [],
    });
    const wrapper = root.querySelector<HTMLElement>("[data-component]")!;
    expect(wrapper.className).toContain("flex-1");
    expect(wrapper.className).toContain("min-w-0");
    const stamp = wrapper.querySelector<HTMLElement>("[data-stamp]")!;
    expect(stamp.dataset.stamp).toBe("sm");
    expect(stamp.dataset.doc).toBe("D-1");
  });

  it("keeps its width on the right, in the projection's order", async () => {
    const root = await mount({
      left: [],
      controls: [control("archive"), component("owner"), control("save")],
      bands: [],
    });
    const wrapper = root.querySelector<HTMLElement>("[data-component]")!;
    expect(wrapper.className).toContain("shrink-0");
    expect(wrapper.className).not.toContain("flex-1");
    const order = [...root.querySelectorAll<HTMLElement>("[data-label], [data-component]")].map(
      (el) => el.dataset.label ?? "component",
    );
    expect(order).toEqual(["archive", "component", "save"]);
  });
});

describe("props on a control", () => {
  // The stub spreads every bound prop as an attribute; a boolean lands as `""`/absent or `"true"`/`"false"`.
  const attr = (root: HTMLElement, label: string, name: string) =>
    root.querySelector<HTMLElement>(`[data-label="${label}"]`)!.getAttribute(name);
  const flag = (root: HTMLElement, label: string, name: string) => {
    const value = attr(root, label, name);
    return value !== null && value !== "false";
  };

  it("binds the forwarded props over the host's defaults, with the item's label and icon on top", async () => {
    const root = await mount({
      left: [{ ...control("watch", { variant: "solid", class: "italic" }), item: { name: "watch", label: "Watch", icon: "lucide-eye" } }],
      controls: [control("export", { theme: "green" })],
      bands: [],
    });
    expect(attr(root, "Watch", "variant")).toBe("solid");
    expect(attr(root, "Watch", "class")).toContain("italic");
    expect(attr(root, "Watch", "iconleft") ?? attr(root, "Watch", "icon-left")).toBe("lucide-eye");
    expect(attr(root, "export", "variant")).toBe("subtle");
    expect(attr(root, "export", "theme")).toBe("green");
  });

  it("keeps Save's disabled and loading the host's, whatever the script wrote", async () => {
    const clean = await mount({
      left: [],
      controls: [control("save", { disabled: false, loading: true, variant: "ghost" })],
      bands: [],
    });
    expect(flag(clean, "save", "disabled")).toBe(true);
    expect(flag(clean, "save", "loading")).toBe(false);
    expect(attr(clean, "save", "variant")).toBe("ghost");

    const busy = await mount(
      { left: [], controls: [control("save", { disabled: true })], bands: [] },
      undefined,
      undefined,
      { dirty: true, saving: true },
    );
    expect(flag(busy, "save", "disabled")).toBe(false);
    expect(flag(busy, "save", "loading")).toBe(true);
  });
});
