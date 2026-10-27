// The list page's act surface: `list.create`, `list.favourite`, `list.customize_quick_filter` and
// `list.delete` run by name through the dispatcher, are drawn from the same items, and are refused without their right.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createApp,
  defineComponent,
  h,
  nextTick,
  ref,
  type App,
  type Ref,
} from "vue";
import { createMemoryHistory, createRouter } from "vue-router";

const page = vi.hoisted(() => ({
  customizing: null as unknown as Ref<boolean>,
  selection: null as unknown as Ref<string[]>,
  selectedAtMount: [] as string[],
}));

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
vi.mock("@framework/ui/experimental/List", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    List: stub("list"),
    ListFooter: stub("footer"),
    ListBulkBar: defineComponent({
      props: { actions: { type: Array, default: () => [] } },
      setup: (props) => () =>
        h(
          "div",
          { "data-stub-bulk-bar": "" },
          (props.actions as { label: string; onClick: () => void }[]).map(
            (action) => h("button", { onClick: action.onClick }, action.label)
          )
        ),
    }),
  };
});
vi.mock("../DeleteDialog.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    default: defineComponent({
      props: { modelValue: Boolean },
      setup: (props) => () =>
        props.modelValue ? h("div", { "data-delete-dialog": "" }) : null,
    }),
  };
});
vi.mock("@/list/useScrollMemory", () => ({ useScrollMemory: () => {} }));
vi.mock("@/list/useListPage", async () => {
  const { computed, ref } = await import("vue");
  return {
    useListPage: () => {
      const empty = () => ref([]);
      page.customizing = ref(false);
      page.selection = ref([...page.selectedAtMount]);
      return {
        filters: empty(),
        sort: empty(),
        columns: empty(),
        quickFilterFields: ref(undefined),
        customizing: page.customizing,
        selection: page.selection,
        pageSize: ref(20),
        rowsKey: () => "",
        rows: empty(),
        loading: ref(false),
        error: ref(null),
        metaError: ref(null),
        seeded: ref(true),
        rowCount: ref(0),
        totalCount: ref(0),
        totalCapped: ref(false),
        totalUnknown: ref(false),
        hasCounts: ref(false),
        hasNextPage: ref(false),
        createValues: computed(() => ({})),
        reload: () => {},
      };
    },
  };
});

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
import DoctypeList from "../DoctypeList.vue";

const addresses = new Addresses({
  doctypes: { Contact: ["contact", "crm"] },
  modules: { crm: "CRM" },
});
const boot = {
  app: "crm",
  shell_base: "/apps/crm",
  prefixes: { crm: { app: "crm", modular: false } },
  read_only_mode: false,
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

let permissions: Record<string, unknown>[];
let starred: { list: boolean; views: string[] };
let toggles: Record<string, unknown>[];
const apps: App[] = [];

beforeEach(() => {
  resetDoctypeMeta();
  clearDataCache();
  setSession(SESSION);
  registerCreateDialog(stub("create-dialog"));
  closeCreates();
  permissions = [ALL_RIGHTS];
  page.selectedAtMount = [];
  starred = { list: false, views: [] };
  toggles = [];
  resetListSettings();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = new URL(String(url), "http://x").pathname;
      if (path === `/api/v2/method/${SETTINGS}`)
        return new Response(
          JSON.stringify({ data: { site: null, user: null, favourites: starred } })
        );
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

async function mount(whileLoading?: () => void, view: string | null = null) {
  shownView.value = view;
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/:doctype", name: "list", component: { render: () => null } },
      {
        path: "/:doctype/:name",
        name: "record",
        component: { render: () => null },
      },
    ],
  });
  registerShell({ boot, addresses, router });
  await router.push("/contact");
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(
    defineComponent({
      render: () => h(DoctypeList, { doctype: "Contact", view: shownView.value }),
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
  it("lists the four built-ins by name while rows are selected", async () => {
    page.selectedAtMount = ["CONT-0001"];
    await mount();
    expect(listActNames()).toEqual([
      "list.create",
      "list.favourite",
      "list.customize_quick_filter",
      "list.delete",
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
    expect(page.customizing.value).toBe(true);
    expect(await denial("list.customize_quick_filter")).toMatchObject({
      reason: "hidden",
    });
  });

  it("runs list.delete into the delete question while rows are selected, and draws it in the bulk bar", async () => {
    const root = await mount();
    expect(await denial("list.delete")).toMatchObject({ reason: "missing" });

    page.selection.value = ["CONT-0001"];
    await nextTick();
    expect(bulkLabels(root)).toEqual(["Delete"]);
    await acts.run("list.delete");
    await nextTick();
    expect(root.querySelector("[data-delete-dialog]")).not.toBeNull();
  });

  it("refuses list.create and list.delete with ActDenied for a user without the rights, and draws neither", async () => {
    permissions = [READ_ONLY];
    page.selectedAtMount = ["CONT-0001"];
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
    expect(listActNames()).toEqual(["list.favourite", "list.customize_quick_filter"]);
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
    expect(toggles).toEqual([{ doctype: "Doctype View", name: "open-contacts", add: false }]);
    expect(root.querySelector("header [data-favourite]")!.getAttribute("aria-pressed")).toBe("false");
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

  it("follows the address from one saved view to the next without a remount", async () => {
    starred = { list: false, views: ["open-contacts"] };
    const root = await mount(undefined, "open-contacts");
    const star = () => root.querySelector("header [data-favourite]")!;
    expect(star().getAttribute("aria-pressed")).toBe("true");

    shownView.value = "closed-contacts";
    await settle();
    expect(star().getAttribute("aria-pressed")).toBe("false");
    await acts.run("list.favourite");
    await settle();
    expect(toggles).toEqual([{ doctype: "Doctype View", name: "closed-contacts", add: true }]);
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
