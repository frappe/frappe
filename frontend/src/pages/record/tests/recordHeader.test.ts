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

const control = (name: string) => ({ kind: "button" as const, item: { name, label: name } });

type Favourites = { favourites: { id: string; name: string }[]; favourited: boolean };

async function mount(
  projection: HeaderProjection,
  favourites: Favourites = { favourites: [], favourited: false },
  onRun: (item: any) => void = () => {},
) {
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () =>
        h(RecordHeader, { projection, dirty: false, saving: false, ...favourites, onRun }),
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
