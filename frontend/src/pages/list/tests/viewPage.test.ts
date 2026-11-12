// A view is laid out by its type's renderer: the list page draws the one registered for the view's
// type in the rows area, and hands it the view and the host.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

function stub(name: string) {
  return defineComponent({
    setup: () => () => h("div", { [`data-stub-${name}`]: "" }),
  });
}

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    default: defineComponent({
      setup:
        (_, { slots }) =>
        () => [slots.header?.(), slots.default?.()],
    }),
    pageGutter: "",
  };
});
vi.mock("@framework/ui/QuickFilter", () => ({
  QuickFilter: stub("quick-filter"),
}));
vi.mock("@framework/ui/Filter", () => ({ Filter: stub("filter") }));
vi.mock("@framework/ui/SortBy", () => ({ SortBy: stub("sort") }));
vi.mock("@/list/useListPage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/list/useListPage")>()),
  useListPage: (await import("./fakeListPage")).useListPage,
}));

import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { viewRenderers } from "@/contributions/registry";
import type { SavedView } from "@/list/savedView";
import { clearRenderers } from "../renderer";
import { registerShell } from "@/router/routeFor";
import ViewPage from "../ViewPage.vue";

const addresses = new Addresses({
  doctypes: { Contact: ["contact", "crm"] },
  modules: { crm: "CRM" },
});
const boot = {
  app: "crm",
  app_title: "CRM",
  session: { user: { name: "jane@example.com" } },
  shell_base: "/apps/crm",
  prefixes: { crm: { app: "crm", modular: false } },
  bulk_actions: true,
  bulk_operation_limit: 500,
} as unknown as Boot;

const apps: App[] = [];
const seen = vi.hoisted(() => ({ props: [] as Record<string, any>[] }));

const KanbanRenderer = defineComponent({
  props: ["view", "host"],
  setup(props) {
    seen.props.push(props);
    return () =>
      h("div", { "data-renderer": "kanban", "data-type": props.view.type });
  },
});

const BOARD: SavedView = {
  key: "board",
  label: "Board",
  type: "Kanban",
  layer: "own",
  applies: true,
};

beforeEach(() => {
  seen.props = [];
  vi.stubGlobal("fetch", async () => new Response("{}", { status: 404 }));
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  clearRenderers();
  delete viewRenderers.Kanban;
  vi.unstubAllGlobals();
});

async function mount(opened: SavedView) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/", name: "home", component: { render: () => null } },
      { path: "/:doctype", name: "list", component: { render: () => null } },
    ],
  });
  registerShell({ boot, addresses, router });
  await router.push("/contact");
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () => h(ViewPage, { doctype: "Contact", opened }),
    }),
  );
  app.use(router).provide("addresses", addresses).provide("boot", boot);
  app.mount(root);
  apps.push(app);
  for (let turn = 0; turn < 3; turn++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await nextTick();
  }
  return root;
}

describe("the renderer of a view's type", () => {
  it("draws in the rows area, under the page's controls, handed the view and the host", async () => {
    viewRenderers.Kanban = async () => KanbanRenderer;
    const root = await mount(BOARD);

    expect(
      root.querySelector("[data-renderer='kanban']")?.getAttribute("data-type"),
    ).toBe("Kanban");
    expect(root.querySelector("[data-stub-filter]")).not.toBeNull();
    expect(root.textContent).toContain("Board");
    expect(seen.props[0].view).toMatchObject({
      doctype: "Contact",
      key: "board",
      type: "Kanban",
      layer: "own",
    });
    expect(Object.keys(seen.props[0].host).sort()).toEqual([
      "acts",
      "bar",
      "controls",
      "lists",
      "onCreate",
      "selecting",
    ]);
  });

  it("is one load per type, however many views draw it", async () => {
    const load = vi.fn(async () => KanbanRenderer);
    viewRenderers.Kanban = load;
    await mount(BOARD);
    await mount({ ...BOARD, key: "other" });

    expect(load).toHaveBeenCalledOnce();
  });

  it("is the not found state for a type with no renderer", async () => {
    const root = await mount(BOARD);

    expect(
      root.querySelector("[data-page-state]")?.getAttribute("data-page-state"),
    ).toBe("notFound");
    expect(root.querySelector("[data-renderer]")).toBeNull();
  });
});
