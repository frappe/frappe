// The list page's act surface: its built-ins run by name through the dispatcher, are drawn from
// the same items, and are refused without their right.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import { createMemoryHistory, createRouter, type Router } from "vue-router";

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
        () =>
          [h("header", slots.header?.()), slots.default?.()],
    }),
    pageGutter: "",
  };
});
vi.mock("@framework/ui/QuickFilter", () => ({
  QuickFilter: stub("quick-filter"),
}));
vi.mock("@framework/ui/Filter", () => ({ Filter: stub("filter") }));
vi.mock("@framework/ui/SortBy", () => ({ SortBy: stub("sort") }));
vi.mock("@framework/ui/ColumnSettings", () => ({
  ColumnSettings: stub("columns"),
}));
vi.mock("@framework/ui/experimental/List", () => ({
  List: stub("list"),
  ListFooter: stub("footer"),
}));
vi.mock("../BulkBar.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    default: defineComponent({
      props: { layout: { type: Object, required: true } },
      setup: (props) => () =>
        h(
          "div",
          { "data-stub-bulk-bar": "" },
          [...props.layout.buttons, props.layout.trash]
            .filter(Boolean)
            .map((entry) => h("button", { onClick: entry.onClick }, entry.label))
        ),
    }),
  };
});
vi.mock("../DeleteDialog.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    __esModule: true,
    default: defineComponent({
      props: { modelValue: Boolean },
      setup: (props) => () =>
        props.modelValue ? h("div", { "data-delete-dialog": "" }) : null,
    }),
  };
});
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/list/useListPage")>()),
  useListPage: (await import("./fakeListPage")).useListPage,
}));
vi.mock("@/list/useListView", async () => ({
  useListView: (await import("./fakeListPage")).useListView,
}));

import { Addresses } from "@/addresses";
import { acts, ActDenied } from "@/acts/dispatcher";
import type { Boot } from "@/boot";
import { registerShell } from "@/router/routeFor";
import {
  closeCreates,
  createRequests,
  registerCreateDialog,
} from "@/shell/create";
import type { Session } from "@framework/ui/api";
import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetSession, setSession } from "@framework/ui/useSession";
import { resetListSettings } from "@/list/useListSettings";
import { PLAIN_LIST } from "@/list/useListPage";
import type { ListPageApi } from "@/listPage/types";
import { createListPageLists } from "@/listPage/createListPage";
import { useListActs } from "../listActs";
import ViewPage from "../ViewPage.vue";
import {
  fake,
  installListRenderer,
  resetFake,
} from "./fakeListPage";

const addresses = new Addresses({
  doctypes: { Contact: ["contact", "crm"] },
  modules: { crm: "CRM" },
});
const boot = {
  app: "crm",
  shell_base: "/apps/crm",
  prefixes: { crm: { app: "crm", modular: false } },
  read_only_mode: false,
  bulk_actions: true,
  bulk_operation_limit: 500,
} as unknown as Boot;

const SESSION: Session = {
  user: {
    name: "test@example.com",
    full_name: "Test",
    email: "test@example.com",
    user_image: null,
    document_follow_notify: false,
  },
  roles: ["Sales User", "Desk User"],
  lang: "en",
  timezone: "Asia/Kolkata",
  defaults: {},
};

const ALL_RIGHTS = {
  role: "Sales User",
  permlevel: 0,
  read: 1,
  write: 1,
  create: 1,
  delete: 1,
};
const READ_ONLY = { role: "Sales User", permlevel: 0, read: 1 };

const SETTINGS = "frappe.desk.doctype.doctype_view.api.get";
const TOGGLE = "frappe.desk.doctype.favourite.favourite.toggle_favourite";
const DEFAULT_VIEW = "frappe.desk.doctype.default_view.api";

let permissions: Record<string, unknown>[];
let starred: { list: boolean; views: string[] };
let toggles: Record<string, unknown>[];
let defaultCalls: { method: string; body: Record<string, unknown> }[];
let defaultAnswer: string | null;
const apps: App[] = [];

beforeEach(async () => {
  resetFake();
  await installListRenderer();
  resetDoctypeMeta();
  clearDataCache();
  setSession(SESSION);
  registerCreateDialog(stub("create-dialog"));
  closeCreates();
  permissions = [ALL_RIGHTS];
  starred = { list: false, views: [] };
  toggles = [];
  defaultCalls = [];
  defaultAnswer = null;
  boot.default_views = {};
  resetListSettings();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = new URL(String(url), "http://x").pathname;
      if (path === `/api/v2/method/${SETTINGS}`)
        return new Response(
          JSON.stringify({ data: { site: null, user: null, favourites: starred } })
        );
      if (path.startsWith(`/api/v2/method/${DEFAULT_VIEW}.`)) {
        const method = path.split(".").pop()!;
        defaultCalls.push({ method, body: JSON.parse(String(init?.body)) });
        return new Response(defaultAnswer ? JSON.stringify({ data: defaultAnswer }) : "{}");
      }
      if (path === `/api/v2/method/${TOGGLE}`) {
        toggles.push(JSON.parse(String(init?.body)));
        // A whitelisted method that returns nothing answers with no `data` at all.
        return new Response("{}");
      }
      if (path !== "/api/v2/doctype/Contact/meta")
        return new Response(
          JSON.stringify({ errors: [{ type: "NotFound", message: path }] }),
          { status: 404 }
        );
      return new Response(
        JSON.stringify({ data: { name: "Contact", fields: [], permissions } })
      );
    })
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  closeCreates();
  resetSession();
  vi.unstubAllGlobals();
});

async function settle() {
  for (let turn = 0; turn < 3; turn++) {
    await new Promise((resolve) => setTimeout(resolve, 0));
    await nextTick();
  }
}

const shownView = ref<string | null>(null);
let mounted: Router | null = null;
const router = () => mounted!;

async function mount(whileLoading?: () => void, view: string | null = null) {
  shownView.value = view;
  const router = (mounted = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/:doctype", name: "list", component: { render: () => null } },
      { path: "/:doctype/view/:key", name: "saved-view", component: { render: () => null } },
      {
        path: "/:doctype/:name",
        name: "record",
        component: { render: () => null },
      },
    ],
  }));
  registerShell({ boot, addresses, router });
  await router.push("/contact");
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () =>
        h(ViewPage, {
          // As List.vue keys it: another view is another page state.
          key: `Contact/${shownView.value ?? "list"}`,
          doctype: "Contact",
          opened: shownView.value
            ? { ...PLAIN_LIST, key: shownView.value, label: shownView.value, layer: "user" }
            : PLAIN_LIST,
        }),
    })
  );
  app.use(router).provide("addresses", addresses).provide("boot", boot);
  app.mount(root);
  apps.push(app);
  whileLoading?.();
  await settle();
  return root;
}

function listActNames() {
  return acts
    .available()
    .map((act) => act.name)
    .filter((name) => name.startsWith("list."));
}

function bulkLabels(root: HTMLElement) {
  return [...root.querySelectorAll("[data-stub-bulk-bar] button")].map(
    (button) => button.textContent
  );
}

async function denial(name: string) {
  return acts.run(name).then(
    () => null,
    (error) => error
  );
}

describe("the list surface", () => {
  it("lists the five built-ins by name while rows are selected", async () => {
    fake.selectedAtMount = ["CONT-0001"];
    await mount();
    expect(listActNames()).toEqual([
      "list.create",
      "list.favourite",
      "list.open_view",
      "list.set_default_view",
      "list.clear_default_view",
      "list.customize_quick_filter",
      "list.delete",
      "list.open_bulk_menu",
      "list.clear_selection",
    ]);
  });

  it("runs list.create into the Create dialog for the list's doctype", async () => {
    await mount();
    void acts.run("list.create");
    await settle();
    expect(createRequests.value).toHaveLength(1);
    expect(createRequests.value[0]).toMatchObject({ doctype: "Contact" });
  });

  it("runs list.customize_quick_filter, which is then hidden while customizing", async () => {
    await mount();
    await acts.run("list.customize_quick_filter");
    await nextTick();
    expect(fake.state.customizing.value).toBe(true);
    expect(await denial("list.customize_quick_filter")).toMatchObject({
      reason: "hidden",
    });
  });

  it("runs list.delete into the delete question while rows are selected, and draws it in the bulk bar", async () => {
    const root = await mount();
    expect(await denial("list.delete")).toMatchObject({ reason: "missing" });

    fake.state.selection.value = ["CONT-0001"];
    await nextTick();
    expect(bulkLabels(root)).toEqual(["Delete"]);
    await acts.run("list.delete");
    await vi.waitFor(() => expect(root.querySelector("[data-delete-dialog]")).not.toBeNull());
  });

  it("gives a list act the list page: doctype, view, the selection as read now and reload", async () => {
    await mount();
    fake.state.selection.value = ["CONT-0001"];
    await nextTick();

    const page = acts.contextOf("list") as ListPageApi;
    expect(page).toMatchObject({ doctype: "Contact", selection: ["CONT-0001"] });
    expect(page.view.key).toBe("list");
    expect(Object.isFrozen(page.selection)).toBe(true);
    page.reload();
    expect(fake.reload).toHaveBeenCalledTimes(1);
    fake.state.selection.value = [];
    expect(page.selection).toEqual([]);
  });

  it("refuses list.create and list.delete with ActDenied for a user without the rights, and draws neither", async () => {
    permissions = [READ_ONLY];
    fake.selectedAtMount = ["CONT-0001"];
    const root = await mount();

    for (const name of ["list.create", "list.delete"]) {
      const error = await denial(name);
      expect(error).toBeInstanceOf(ActDenied);
      expect(error).toMatchObject({ act: name, reason: "right" });
    }
    expect(createRequests.value).toHaveLength(0);
    expect(root.querySelector("[data-delete-dialog]")).toBeNull();
    expect(
      [...root.querySelectorAll("header button")].map((button) =>
        button.textContent?.trim()
      )
    ).not.toContain("Create");
    expect(bulkLabels(root)).toEqual([]);
    expect(listActNames()).toEqual([
      "list.favourite",
      "list.open_view",
      "list.set_default_view",
      "list.clear_default_view",
      "list.customize_quick_filter",
      "list.clear_selection",
    ]);
  });

  it("runs list.favourite on the plain list, stars the list and draws the star filled", async () => {
    const root = await mount();
    const star = () => root.querySelector("header [data-favourite]")!;
    expect(star().getAttribute("aria-pressed")).toBe("false");

    await acts.run("list.favourite");
    await settle();
    expect(toggles).toEqual([{ doctype: "DocType", name: "Contact", add: true }]);
    expect(star().getAttribute("aria-pressed")).toBe("true");
    expect(acts.find("list.favourite")?.label).toBe("Remove from favourites");

    (star() as HTMLElement).click();
    await settle();
    expect(toggles[1]).toEqual({ doctype: "DocType", name: "Contact", add: false });
    expect(star().getAttribute("aria-pressed")).toBe("false");
  });

  it("stars the saved view on a saved view's address, and reads its state from the settings read", async () => {
    starred = { list: true, views: ["open-contacts"] };
    const root = await mount(undefined, "open-contacts");
    expect(root.querySelector("header [data-favourite]")!.getAttribute("aria-pressed")).toBe("true");

    await acts.run("list.favourite");
    await settle();
    expect(toggles).toEqual([{ doctype: "DocType", name: "Contact", view: "open-contacts", add: false }]);
    expect(root.querySelector("header [data-favourite]")!.getAttribute("aria-pressed")).toBe("false");
  });

  it("runs list.open_view to the saved view's address by its key", async () => {
    await mount();

    await acts.run("list.open_view", { key: "open-contacts" });
    await settle();

    expect(router().currentRoute.value.fullPath).toBe("/contact/view/open-contacts");
    expect(acts.available().find((act) => act.name === "list.open_view")?.palette).toBe(false);
  });

  it("refuses list.open_view without a key and stays on the list", async () => {
    await mount();

    await expect(acts.run("list.open_view", {})).rejects.toThrow("Name the view to open by its key.");
    expect(router().currentRoute.value.fullPath).toBe("/contact");
  });

  it("runs list.set_default_view on one layer and keeps the person's default in boot for the router", async () => {
    await mount();
    defaultAnswer = "open-contacts";

    await acts.run("list.set_default_view", { key: "open-contacts", scope: "site" });

    expect(defaultCalls).toEqual([
      { method: "save", body: { doctype: "Contact", key: "open-contacts", scope: "site", app: "crm" } },
    ]);
    expect(boot.default_views).toEqual({ Contact: "open-contacts" });
    expect(acts.available().find((act) => act.name === "list.set_default_view")?.palette).toBe(false);
  });

  it("runs list.clear_default_view and keeps the default of the layer left, or none", async () => {
    boot.default_views = { Contact: "my-contacts" };
    await mount();
    defaultAnswer = "open-contacts";

    await acts.run("list.clear_default_view", { scope: "user" });
    expect(boot.default_views).toEqual({ Contact: "open-contacts" });

    defaultAnswer = null;
    await acts.run("list.clear_default_view", { scope: "site" });
    expect(defaultCalls.map((call) => call.body)).toEqual([
      { doctype: "Contact", scope: "user", app: "crm" },
      { doctype: "Contact", scope: "site", app: "crm" },
    ]);
    expect(boot.default_views).toEqual({});
  });

  it("refuses a default view act without a key or a layer, and asks nothing", async () => {
    await mount();

    await expect(acts.run("list.set_default_view", { scope: "user" })).rejects.toThrow(
      "Name the view to open by its key."
    );
    await expect(acts.run("list.set_default_view", { key: "list", scope: "team" })).rejects.toThrow(
      "Name the default's layer: user or site."
    );
    await expect(acts.run("list.clear_default_view", {})).rejects.toThrow(
      "Name the default's layer: user or site."
    );
    expect(defaultCalls).toEqual([]);
  });

  it("toggles twice on two quick clicks, each turn reading the state the one before left", async () => {
    const root = await mount();
    const star = root.querySelector("header [data-favourite]") as HTMLElement;
    star.click();
    star.click();
    await settle();
    expect(toggles.map((call) => call.add)).toEqual([true, false]);
    expect(star.getAttribute("aria-pressed")).toBe("false");
  });

  it("gives the next saved view its own page state, with its own star", async () => {
    starred = { list: false, views: ["open-contacts"] };
    const root = await mount(undefined, "open-contacts");
    const star = () => root.querySelector("header [data-favourite]")!;
    expect(star().getAttribute("aria-pressed")).toBe("true");

    shownView.value = "closed-contacts";
    await settle();
    expect(star().getAttribute("aria-pressed")).toBe("false");
    await acts.run("list.favourite");
    await settle();
    expect(toggles).toEqual([{ doctype: "DocType", name: "Contact", view: "closed-contacts", add: true }]);
  });

  it("draws no star until the settings read says what is starred", async () => {
    let answer: (response: Response) => void = () => {};
    const real = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (url, init) =>
      String(url).includes(SETTINGS)
        ? new Promise<Response>((resolve) => (answer = resolve))
        : real(url, init)
    );
    const root = await mount();
    expect(root.querySelector("header [data-favourite]")).toBeNull();
    expect(listActNames()).not.toContain("list.favourite");

    answer(new Response(JSON.stringify({ data: { site: null, user: null, favourites: { list: true, views: [] } } })));
    await settle();
    expect(root.querySelector("header [data-favourite]")!.getAttribute("aria-pressed")).toBe("true");
  });

  it("draws no star when the settings read fails, since it cannot say what is starred", async () => {
    const real = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (url, init) =>
      String(url).includes(SETTINGS)
        ? new Response(JSON.stringify({ errors: [{ type: "Error", message: "down" }] }), { status: 500 })
        : real(url, init)
    );
    const root = await mount();
    expect(root.querySelector("header [data-favourite]")).toBeNull();
    expect(listActNames()).not.toContain("list.favourite");

    vi.mocked(fetch).mockImplementation(real);
    for (const app of apps.splice(0)) app.unmount();
    const again = await mount();
    expect(again.querySelector("header [data-favourite]")).not.toBeNull();
  });

  it("keeps the star as it was when the server refuses", async () => {
    const root = await mount();
    vi.mocked(fetch).mockImplementationOnce(
      async () =>
        new Response(JSON.stringify({ errors: [{ type: "PermissionError", message: "No" }] }), {
          status: 403,
        })
    );
    await expect(acts.run("list.favourite")).rejects.toBeTruthy();
    await settle();
    expect(root.querySelector("header [data-favourite]")!.getAttribute("aria-pressed")).toBe("false");
  });

  it("waits for the meta before it checks a right", async () => {
    await mount(() => void acts.run("list.create"));
    await settle();
    expect(createRequests.value).toHaveLength(1);
  });

  it("takes the surface off the dispatcher when the page goes", async () => {
    await mount();
    for (const app of apps.splice(0)) app.unmount();
    expect(listActNames()).toEqual([]);
  });
});

describe("a renderer's acts", () => {
  const moveCard = {
    item: { name: "move_card", label: "Move card", run: () => {} },
    hidden: false,
  };

  async function mountActs(type?: string) {
    const host = {
      list: {
        page: {},
        engine: { hold: <T,>(work: () => T) => Promise.resolve(work()) },
        lists: createListPageLists(),
        attach: () => {},
      } as never,
      permissions: {
        passes: () => true,
        loading: () => false,
        ready: () => Promise.resolve(),
      } as never,
      create: () => {},
      customizeQuickFilter: () => {},
      customizing: () => false,
      starsLoaded: () => true,
      favourited: () => false,
      toggleFavourite: () => {},
      openView: () => {},
      setDefaultView: () => {},
      clearDefaultView: () => {},
    };
    const app = createApp(
      defineComponent({
        setup() {
          useListActs(host, type).renderer(() => [moveCard], {
            rows: () => [],
            selection: () => [],
            reload: () => {},
          });
          return () => null;
        },
      })
    );
    app.provide("boot", boot).provide("addresses", addresses);
    app.mount(document.body.appendChild(document.createElement("div")));
    apps.push(app);
    await settle();
  }

  const namesWith = (act: string) =>
    acts
      .available()
      .map((one) => one.name)
      .filter((name) => name.endsWith(`.${act}`));

  it("land on the type's own surface, not on list", async () => {
    await mountActs("Kanban");
    expect(namesWith("move_card")).toEqual(["kanban.move_card"]);
    expect(listActNames()).toContain("list.create");
  });

  it("land on list for the List type", async () => {
    await mountActs("List");
    expect(namesWith("move_card")).toEqual(["list.move_card"]);
  });

  it("land on list when no type is named, as the List type's do", async () => {
    await mountActs();
    expect(namesWith("move_card")).toEqual(["list.move_card"]);
  });
});
