// The header's two zones: crumb runs and the star left; a script's controls, `⋯`, then Save right.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, createApp, defineComponent, h, nextTick, ref } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

// Hoisted with the mocks, so each factory can reach it.
const { Plain, metas, metaHeld } = vi.hoisted(() => ({
  metas: {} as Record<string, any>,
  metaHeld: { until: Promise.resolve() },
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
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async (doctype: string) => {
    if (doctype === "CRM Deal") await metaHeld.until;
    return { data: metas[doctype] ?? null, children: [] };
  }),
}));

import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { setSession } from "@framework/ui/useSession";
import { resetUserRoles } from "@framework/ui/useUserRoles";
import { acts } from "@/acts/dispatcher";
import RecordHeader from "../RecordHeader.vue";
import { projectRecordHeader } from "../recordHeaderProjection";
import type { HeaderItem, HeaderProjection } from "@/recordPage";
import { createRecordPage, type RecordPageHost } from "@/recordPage/createRecordPage";
import { withRegisteringSource } from "@/recordPage/context";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import type { AuthoredHandlers } from "@/recordPage/types";

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

const band = {
  group: "actions",
  items: [{ item: { name: "delete", label: "Delete" }, source: "builtin", props: {}, members: [] }],
};

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

  it("binds a dropdown trigger's props under the item's label, keeping the chevron by default", async () => {
    const root = await mount({
      left: [],
      controls: [
        { kind: "dropdown", item: { name: "tools", label: "Tools" }, source: "test", props: { variant: "ghost" }, members: [] },
      ],
      bands: [],
    });
    expect(attr(root, "Tools", "variant")).toBe("ghost");
    expect(attr(root, "Tools", "iconright") ?? attr(root, "Tools", "icon-right")).toBe("lucide-chevron-down");
  });

  it("hands a script's tooltip to Save's own button, beside the host's clean-record tooltip", async () => {
    const root = await mount({
      left: [],
      controls: [control("save", { tooltip: "Writes the record" })],
      bands: [],
    });
    expect(attr(root, "save", "tooltip")).toBe("Writes the record");
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

describe("an item's right", () => {
  const controllers: ReturnType<typeof createRecordPage>[] = [];

  beforeEach(() => {
    resetRegistry();
    resetDoctypeMeta();
    resetUserRoles();
    for (const doctype of Object.keys(metas)) delete metas[doctype];
  });

  afterEach(() => {
    for (const controller of controllers.splice(0)) controller.leave();
    metaHeld.until = Promise.resolve();
  });

  async function drawn(handlers: AuthoredHandlers, perms: Record<string, number>) {
    await withRegisteringSource("crm", async () => registerRecordPage("CRM Lead", handlers));
    const controller = createRecordPage({
      doctype: "CRM Lead",
      docname: "CRM-LEAD-1",
      doc: ref({}),
      saved: ref({}),
      meta: ref({ name: "CRM Lead", fields: [] }),
      perms: () => perms,
      isDirty: () => false,
      activeTab: () => "details",
      activateTab: () => {},
      save: async () => {},
      reload: async () => {},
      router: {} as any,
      activityRows: () => [],
      scrollToActivity: async () => true,
      reloadActivity: async () => {},
      fileRows: () => [],
      reloadFiles: async () => {},
    } as RecordPageHost);
    controllers.push(controller);
    await controller.refresh();
    const projection = computed(() =>
      projectRecordHeader(controller.header.resolve(), controller.allows)
    );
    const root = document.createElement("div");
    document.body.appendChild(root);
    const app = createApp(
      defineComponent({ render: () => h(RecordHeader, { projection: projection.value, page }) })
    );
    app.mount(root);
    mounted.push(app);
    await nextTick();
    return root;
  }

  const purge = {
    onRefresh: (page: any) =>
      page.header.add({ name: "purge", label: "Purge", display: "button", right: "delete", run: () => {} }),
  };

  it("draws a script's item only for a reader who holds its right", async () => {
    expect(rightHand(await drawn(purge, { read: 1, delete: 0 }))).not.toContain("Purge");
    expect(rightHand(await drawn(purge, { read: 1, delete: 1 }))).toContain("Purge");
  });

  it("hides a dropdown whose right fails, and its members from the dispatcher too", async () => {
    const menu = {
      onRefresh: (page: any) => {
        page.header.add({ name: "more", label: "More", display: "dropdown", right: "delete" });
        page.header.add({ name: "archive", label: "Archive", group: "more", run: () => {} });
      },
    };
    expect(rightHand(await drawn(menu, { read: 1, delete: 0 }))).not.toContain("More");
    expect(acts.find("header.archive")).toBeUndefined();
    expect(rightHand(await drawn(menu, { read: 1, delete: 1 }))).toContain("More");
    expect(acts.find("header.archive")).toBeDefined();
  });

  it("draws an item with a right on another doctype once that right settles and passes", async () => {
    setSession({
      user: { name: "sales@example.com", full_name: "Sales", email: "sales@example.com", user_image: null, document_follow_notify: false },
      roles: ["Sales User"],
      lang: "en",
      timezone: "Asia/Kolkata",
      defaults: {},
    });
    metas["CRM Deal"] = { name: "CRM Deal", permissions: [{ role: "Sales User", permlevel: 0, read: 1, create: 1 }] };
    const convert = {
      onRefresh: (page: any) =>
        page.header.add({
          name: "convert",
          label: "Convert",
          display: "button",
          right: { doctype: "CRM Deal", ptype: "create" },
          run: () => {},
        }),
    };
    let release!: () => void;
    metaHeld.until = new Promise((resolve) => (release = resolve));
    const root = await drawn(convert, { read: 1 });
    expect(rightHand(root)).not.toContain("Convert");

    release();
    await vi.waitFor(() => expect(rightHand(root)).toContain("Convert"));
  });
});
