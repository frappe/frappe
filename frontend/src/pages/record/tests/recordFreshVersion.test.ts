// A return visit after a Client Script or DocType change paints the old version, then the new one
// in the step that applies the record's re-read, with no skeleton.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView, type Router } from "vue-router";

const scripts = vi.hoisted(() => ({ runs: [] as string[] }));

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
    }),
  };
});

// Node cannot import a blob-URL module; a row's `script` names the version it stands for.
vi.mock("@/recordPage/evaluateClientScript", () => ({
  evaluateClientScript: async (row: { script: string }) => ({
    onRefresh(page: any) {
      scripts.runs.push(row.script);
      page.quickActions.add({ name: "version", label: `${row.script}|${page.doc.title}` });
    },
  }),
}));

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { clearDataCache } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts, watchClientScripts } from "@/recordPage/clientScripts";
import { resetFormLayouts } from "@/recordPage/formLayoutSource/useFormLayout";
import { resetRegistry } from "@/recordPage/registry";
import { createShellRouter } from "@/router";
import { registerShell, routeFor } from "@/router/routeFor";
import { watchDoctypeUpdates } from "@/shell/doctypeUpdates";

const OLD = "2026-09-25 10:00:00.000000";
const NEW = "2026-09-25 11:00:00.000000";
const GET_CLIENT_SCRIPTS = "frappe.custom.doctype.client_script.client_script.get_client_scripts";
const GET_FORM_LAYOUTS = "frappe.desk.doctype.form_layout.form_layout.get_form_layouts";

interface Gate {
  opened: Promise<void>;
  open: () => void;
}

function gate(): Gate {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

function metaWith(statusLabel: string) {
  return {
    name: "Note",
    title_field: "title",
    fields: [
      { fieldname: "title", fieldtype: "Data", label: "Title" },
      { fieldname: "status", fieldtype: "Data", label: statusLabel },
    ],
  };
}

function layoutOf(fields: string[]) {
  return [{ name: "details", label: "Details", sections: [{ columns: [{ fields }] }] }];
}

/** What the server holds and how it answers; a test moves it between visits. */
const server = {
  doc: {} as Record<string, any>,
  meta: metaWith("Status"),
  details: ["title"],
  script: "v1",
  holdRecord: null as Gate | null,
  holdScripts: null as Gate | null,
  holdLayouts: null as Gate | null,
  requests: [] as string[],
};

async function answer(url: URL): Promise<unknown> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return { data: server.meta };
  if (path === `/api/v2/method/${GET_CLIENT_SCRIPTS}`) {
    await server.holdScripts?.opened;
    return { data: { scripts: [{ name: "Note Script", script: server.script }], can_write: false } };
  }
  if (path === `/api/v2/method/${GET_FORM_LAYOUTS}`) {
    await server.holdLayouts?.opened;
    if (url.searchParams.get("type") !== "Details") return { data: { layouts: [], fallback: [] } };
    const layout = layoutOf(server.details);
    return { data: { layouts: [{ name: 1, condition: null, layout }], fallback: layout } };
  }
  if (path.endsWith("/activity")) return { data: { activities: [], next: null } };
  if (path.startsWith("/api/v2/document/Note/")) {
    await server.holdRecord?.opened;
    return {
      data: { ...server.doc },
      permissions: { read: 1, write: 1 },
      assignments: [],
      shares: [],
      tags: [],
      favourites: [],
      follows: false,
      users: {},
      link_titles: {},
      attachments: [],
      seen: [],
    };
  }
  return { data: null };
}

/** The realtime socket the page and the shell listen on; `emit` plays a server event. */
const socket = {
  handlers: {} as Record<string, Set<(payload: unknown) => void>>,
  emit(event: string, payload?: unknown) {
    socket.handlers[event]?.forEach((handler) => handler(payload));
  },
  on(event: string, handler: (payload: unknown) => void) {
    (socket.handlers[event] ??= new Set()).add(handler);
  },
  off(event: string, handler: (payload: unknown) => void) {
    socket.handlers[event]?.delete(handler);
  },
};

const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  session: { user: { name: "test@example.com", email: "test@example.com" } },
} as unknown as Boot;
const addresses = new Addresses({ doctypes: { Note: ["note", "desk"] }, modules: { desk: "Desk" } });
const apps: ReturnType<typeof createApp>[] = [];
const stops: (() => void)[] = [];
let visits = 0;
let name = "";

beforeEach(() => {
  name = `N-${++visits}`;
  server.doc = { doctype: "Note", name, title: "First", status: "Open", modified: OLD };
  server.meta = metaWith("Status");
  server.details = ["title"];
  server.script = "v1";
  server.holdRecord = null;
  server.holdScripts = null;
  server.holdLayouts = null;
  server.requests = [];
  scripts.runs = [];
  socket.handlers = {};
  resetClientScripts();
  resetDoctypeMeta();
  resetFormLayouts();
  resetUserRoles();
  stops.push(watchClientScripts(socket), watchDoctypeUpdates(socket));
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      server.requests.push(`${init?.method ?? "GET"} ${decodeURIComponent(url.pathname)}`);
      return new Response(JSON.stringify(await answer(url)), { status: 200 });
    }),
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  for (const stop of stops.splice(0)) stop();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetRegistry();
  clearDataCache();
});

async function settle() {
  for (let turn = 0; turn < 10; turn++) {
    await nextTick();
    await new Promise((resolve) => setTimeout(resolve));
  }
}

async function mount(address: string) {
  const router = createShellRouter(boot, addresses);
  registerShell({ boot, addresses, router });
  await router.push(address);
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h(RouterView) }));
  app.use(router);
  app.provide("boot", boot);
  app.provide("addresses", addresses);
  app.provide("socket", socket);
  app.mount(root);
  apps.push(app);
  return { root, router };
}

/** A cold first visit, settled, then the list: the record, its meta, layouts and scripts stay in memory. */
async function visitAndLeave(onFirstVisit?: (root: HTMLElement) => void) {
  const page = await mount(`/note/${name}`);
  await settle();
  onFirstVisit?.(page.root);
  await page.router.push("/note");
  await settle();
  return page;
}

/** Back to the record; resolves once the new page has rendered once, with no timer run. */
async function comeBack(router: Router) {
  await router.push(routeFor("Note", name));
  await nextTick();
}

/** The label the page's Client Script drew: its version and the title it saw. */
function version(root: HTMLElement) {
  const button = [...root.querySelectorAll("button")].find((one) => one.textContent!.includes("|"));
  return button?.textContent!.trim() ?? null;
}

function crumbs(root: HTMLElement) {
  return root.querySelector("[data-crumbs]")?.textContent ?? "";
}

/** The Details form's fields as `fieldname:label`, in order. */
function fields(root: HTMLElement) {
  return [...root.querySelectorAll(".field[data-fieldname]")].map((field) => {
    const label = field.querySelector("label")?.textContent?.trim() ?? "";
    return `${field.getAttribute("data-fieldname")}:${label}`;
  });
}

function hasSkeleton(root: HTMLElement) {
  return Boolean(root.querySelector("[data-record-header-skeleton], [data-record-body-skeleton]"));
}

/** Every element added under `root` that is a skeleton, from now on. */
function watchSkeletons(root: HTMLElement) {
  const seen: Element[] = [];
  const observer = new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.addedNodes)
        if (node instanceof Element && (node.matches(".fui-skeleton") || node.querySelector(".fui-skeleton")))
          seen.push(node);
  });
  observer.observe(root, { childList: true, subtree: true });
  return { seen, stop: () => observer.disconnect() };
}

/** What the page shows after each of the next tasks, through `look`. */
async function everyTask(look: () => string) {
  const seen: string[] = [];
  for (let task = 0; task < 20; task++) {
    await new Promise((resolve) => setTimeout(resolve));
    seen.push(look());
  }
  return seen;
}

describe("a return visit after a Client Script change", () => {
  it("paints with the old script, then the new one in the step that brings the record's re-read", async () => {
    const { root, router } = await visitAndLeave((page) => expect(version(page)).toBe("v1|First"));
    server.script = "v2";
    server.doc = { ...server.doc, title: "Second", modified: NEW };
    socket.emit("client_script_changed", { dt: "Note", view: "Record" });
    server.holdScripts = gate();
    const skeletons = watchSkeletons(root);
    scripts.runs = [];

    await comeBack(router);

    expect(hasSkeleton(root)).toBe(false);
    expect(version(root)).toBe("v1|First");
    await settle();
    expect(crumbs(root)).toContain("First");
    expect(version(root)).toBe("v1|First");

    server.holdScripts.open();
    const seen = await everyTask(() => `${crumbs(root).includes("Second") ? "new" : "old"} ${version(root)}`);

    expect(seen.at(-1)).toBe("new v2|Second");
    expect(seen.every((one) => one === "old v1|First" || one === "new v2|Second")).toBe(true);
    expect(scripts.runs).toEqual(["v1", "v2"]);
    expect(skeletons.seen).toEqual([]);
    skeletons.stop();
  });

  it("runs only the new script on a cold load, never the one it replaces", async () => {
    const { root, router } = await visitAndLeave();
    server.script = "v2";
    socket.emit("client_script_changed", { dt: "Note", view: "Record" });
    name = `${name}-other`;
    server.doc = { ...server.doc, name, title: "Other" };
    server.holdScripts = gate();
    scripts.runs = [];

    await router.push(routeFor("Note", name));
    await settle();
    server.holdScripts.open();
    await settle();

    expect(version(root)).toBe("v2|Other");
    expect(scripts.runs).toEqual(["v2"]);
  });

  it("keeps the old script when the script list cannot be read, and still applies the record's re-read", async () => {
    const { root, router } = await visitAndLeave();
    server.doc = { ...server.doc, title: "Second", modified: NEW };
    socket.emit("client_script_changed", { dt: "Note", view: "Record" });
    const reads = vi.mocked(fetch).getMockImplementation()!;
    vi.mocked(fetch).mockImplementation(async (input, init) => {
      if (String(input).includes(GET_CLIENT_SCRIPTS)) return new Response("{}", { status: 500 });
      return reads(input, init);
    });
    vi.spyOn(console, "error").mockImplementation(() => {});

    await comeBack(router);
    await settle();

    expect(version(root)).toBe("v1|Second");
  });
});

describe("a return visit after a DocType change", () => {
  it("paints with the old meta and layout, then the new ones in the step that brings the record's re-read", async () => {
    const { root, router } = await visitAndLeave((page) => expect(fields(page)).toEqual(["title:Title"]));
    server.details = ["title", "status"];
    server.meta = metaWith("Stage");
    server.doc = { ...server.doc, title: "Second", modified: NEW };
    socket.emit("doctype_update", { doctype: "Note" });
    server.holdLayouts = gate();
    const skeletons = watchSkeletons(root);

    await comeBack(router);

    expect(hasSkeleton(root)).toBe(false);
    expect(fields(root)).toEqual(["title:Title"]);
    await settle();
    expect(crumbs(root)).toContain("First");
    expect(fields(root)).toEqual(["title:Title"]);

    server.holdLayouts.open();
    const seen = await everyTask(
      () => `${crumbs(root).includes("Second") ? "new" : "old"} ${fields(root).join(",")}`,
    );

    expect(seen.at(-1)).toBe("new title:Title,status:Stage");
    expect(seen.every((one) => one === "old title:Title" || one === "new title:Title,status:Stage")).toBe(true);
    expect(skeletons.seen).toEqual([]);
    skeletons.stop();
  });

  it("holds a fresh layout that lands first until the record's re-read lands", async () => {
    const { root, router } = await visitAndLeave();
    server.details = ["title", "status"];
    server.meta = metaWith("Stage");
    server.doc = { ...server.doc, title: "Second", modified: NEW };
    socket.emit("doctype_update", { doctype: "Note" });
    server.holdRecord = gate();

    await comeBack(router);
    await settle();
    expect(crumbs(root)).toContain("First");
    expect(fields(root)).toEqual(["title:Title"]);

    server.holdRecord.open();
    const seen = await everyTask(
      () => `${crumbs(root).includes("Second") ? "new" : "old"} ${fields(root).join(",")}`,
    );

    expect(seen.at(-1)).toBe("new title:Title,status:Stage");
    expect(seen.every((one) => one === "old title:Title" || one === "new title:Title,status:Stage")).toBe(true);
  });

  it("paints a cold load with the new meta and layout only", async () => {
    const { root, router } = await visitAndLeave();
    server.details = ["title", "status"];
    server.meta = metaWith("Stage");
    socket.emit("doctype_update", { doctype: "Note" });
    name = `${name}-other`;
    server.doc = { ...server.doc, name, title: "Other" };
    server.holdLayouts = gate();

    await router.push(routeFor("Note", name));
    await settle();
    expect(fields(root)).toEqual([]);

    server.holdLayouts.open();
    await settle();
    expect(fields(root)).toEqual(["title:Title", "status:Stage"]);
  });
});
