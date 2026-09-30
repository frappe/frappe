// A return within the tab puts back the record's view: tab, form tab, sections, panel sections and scroll.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView, type Router } from "vue-router";
import HistoryItemList from "happy-dom/lib/history/HistoryItemList.js";

const load = vi.hoisted(() => ({ details: [] as unknown[] }));

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
    }),
  };
});

// reka-ui's tabs paint nothing under happy-dom; this one draws a button per tab and the shown panel.
vi.mock("frappe-ui", async (importOriginal) => {
  const { defineComponent, h } = await import("vue");
  return {
    ...((await importOriginal()) as object),
    Tabs: defineComponent({
      props: { tabs: { type: Array, required: true }, modelValue: [String, Number] },
      emits: ["update:modelValue"],
      setup(props, { emit, slots }) {
        return () => {
          const tabs = props.tabs as any[];
          return h("div", { "data-active": String(props.modelValue) }, [
            ...tabs.map((tab) =>
              h("button", { "data-tab": tab.identity ?? tab.value, onClick: () => emit("update:modelValue", tab.value) }),
            ),
            slots["tab-panel"]?.({ tab: tabs.find((tab) => tab.value === props.modelValue) ?? tabs[0] }),
          ]);
        };
      },
    }),
  };
});

vi.mock("@/recordPage", async (importOriginal) => {
  const original = (await importOriginal()) as any;
  const { computed } = await import("vue");
  return {
    ...original,
    useFormLayout: ({ type }: { type: string }) => ({
      layout: computed(() => (type === "Details" ? load.details : [])),
      loading: computed(() => false),
      error: computed(() => null),
      reload: () => {},
      settled: async () => {},
      refreshed: async () => {},
    }),
  };
});

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { clearDataCache, feedListRead, settleTicket, takeTicket } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts } from "@/recordPage/clientScripts";
import { withRegisteringSource } from "@/recordPage/context";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import type { AuthoredHandlers, RecordPageApi } from "@/recordPage/types";
import { createShellRouter } from "@/router";
import { registerShell, routeFor } from "@/router/routeFor";
import { watchDoctypeUpdates } from "@/shell/doctypeUpdates";
import { resetViewMemory } from "../viewMemory";

const OLD = "2026-09-25 10:00:00.000000";
const NEW = "2026-09-25 11:00:00.000000";
const META = {
  name: "Note",
  title_field: "title",
  fields: [
    { fieldname: "title", fieldtype: "Data", label: "Title" },
    { fieldname: "status", fieldtype: "Data", label: "Status" },
  ],
};

/** Two form tabs, so the form draws its strip; each section holds a field, so it draws. */
const DETAILS = [
  {
    name: "main",
    label: "Main",
    sections: [section("summary", "Summary", "title"), section("extra", "Extra", "status")],
  },
  { name: "more", label: "More", sections: [section("notes", "Notes", "title")] },
];

function section(name: string, label: string, fieldname: string) {
  return { name, label, columns: [{ fields: [{ fieldname, fieldtype: "Data", label: fieldname }] }] };
}

interface Gate {
  opened: Promise<void>;
  open: () => void;
}

function gate(): Gate {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

const server = {
  doc: {} as Record<string, any>,
  /** Records other than the one a test visits, by name. */
  others: {} as Record<string, Record<string, any>>,
  meta: META as Record<string, any>,
  holdRecord: null as Gate | null,
  activityReads: 0,
};

async function answer(url: URL, method: string): Promise<[unknown, number]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return [{ data: server.meta }, 200];
  if (path.endsWith("/activity")) {
    server.activityReads++;
    return [{ data: { activities: [], next: null } }, 200];
  }
  if (path.startsWith("/api/v2/document/Note/") && method === "GET") {
    await server.holdRecord?.opened;
    return [recordEnvelope(server.others[path.split("/")[5]] ?? server.doc), 200];
  }
  return [{ data: null }, 200];
}

function recordEnvelope(doc: Record<string, any>) {
  return {
    data: { ...doc },
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
/** What happy-dom lacks: every box is this tall inside, and shows this much of it. */
const box = { scrollHeight: 5000, clientHeight: 500 };
let visits = 0;
let name = "";
let other = "";

// happy-dom keeps the state as given; a browser clones it, and throws on a reactive proxy.
const replaceState = history.replaceState.bind(history);

beforeEach(() => {
  vi.spyOn(history, "replaceState").mockImplementation((state, unused, url) =>
    replaceState(structuredClone(state), unused, url),
  );
  // happy-dom's replaceState drops the entries ahead, which no browser does, and Forward then goes nowhere.
  vi.spyOn(HistoryItemList.prototype, "replace").mockImplementation(function (this: HistoryItemList, item) {
    const index = this.items.indexOf(this.currentItem);
    if (index === -1) throw new Error("Current history item not found");
    this.items[index] = item;
    this.currentItem = item;
  });
  name = `N-${++visits}`;
  other = `N-${++visits}`;
  server.doc = { doctype: "Note", name, title: "First", status: "Open", modified: OLD };
  server.others = { [other]: { doctype: "Note", name: other, title: "Other", status: "Open", modified: OLD } };
  server.meta = META;
  server.holdRecord = null;
  socket.handlers = {};
  load.details = DETAILS;
  box.scrollHeight = 5000;
  localStorage.clear();
  resetClientScripts();
  resetDoctypeMeta();
  resetUserRoles();
  stops.push(watchDoctypeUpdates(socket));
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, get: () => box.scrollHeight });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, get: () => box.clientHeight });
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const [body, status] = await answer(new URL(String(input), "http://x"), init?.method ?? "GET");
      return new Response(JSON.stringify(body), { status });
    }),
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
  for (const stop of stops.splice(0)) stop();
  document.body.innerHTML = "";
  delete (HTMLElement.prototype as any).scrollHeight;
  delete (HTMLElement.prototype as any).clientHeight;
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetRegistry();
  clearDataCache();
  resetViewMemory();
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
  await settle();
  return { root, router };
}

async function leave(router: Router) {
  await router.push("/note");
  await settle();
}

/** A link to the record, or a sidebar or rail click; resolves once the page has rendered once, with no timer run. */
async function comeBack(router: Router, query = "", to = name) {
  await router.push(routeFor("Note", to, { query: Object.fromEntries(new URLSearchParams(query)) }));
  await nextTick();
}

/** Back or Forward: resolves once the popped entry's page has rendered once, with no timer run. */
async function travel(router: Router, delta: number) {
  const landed = new Promise<void>((resolve) => {
    const stop = router.afterEach(() => {
      stop();
      resolve();
    });
  });
  router.go(delta);
  await landed;
  await nextTick();
}

function register(handlers: AuthoredHandlers) {
  return withRegisteringSource("view-restore", async () => registerRecordPage("Note", handlers));
}

/** A labelled panel section, and a quick action that shuts it, as a script's act. */
function notesPanel(page: RecordPageApi) {
  if (!page.panelSections.has("notes")) page.panelSections.add({ name: "notes", label: "Notes" });
  page.quickActions.add({ name: "shut", label: "Shut notes", run: (page) => page.panelSections.close("notes") });
}

async function click(element: Element | null | undefined) {
  (element as HTMLElement).click();
  await settle();
}

function button(root: HTMLElement, label: string) {
  return [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === label);
}

function shownTab(root: HTMLElement) {
  const shown = [...root.querySelectorAll<HTMLElement>("[data-record-tab]")].find((tab) => tab.style.display !== "none");
  return shown?.dataset.recordTab ?? null;
}

function stripButton(root: HTMLElement, tab: string) {
  return root.querySelector(`[data-record-tabs] > div:first-child [data-tab="${tab}"]`);
}

function formTab(root: HTMLElement) {
  return root.querySelector("[data-record-form] [data-active]")?.getAttribute("data-active") ?? null;
}

function formTabButton(root: HTMLElement, tab: string) {
  return root.querySelector(`[data-record-form] [data-tab="${tab}"]`);
}

/** "open" or "closed"; the header carries reka's state at once. */
function formSection(root: HTMLElement, label: string) {
  return formSectionHeader(root, label)?.getAttribute("data-state") ?? null;
}

function formSectionHeader(root: HTMLElement, label: string) {
  return [...root.querySelectorAll<HTMLElement>("[data-record-form] .section-header")].find(
    (one) => one.textContent!.trim() === label,
  );
}

function panelSection(root: HTMLElement, name: string) {
  return root.querySelector(`[data-section="${name}"] button[aria-expanded]`)?.getAttribute("aria-expanded") ?? null;
}

function column(root: HTMLElement, name: string) {
  return root.querySelector<HTMLElement>(`[data-body-column="${name}"] > [data-body-scroll]`);
}

function tabBody(root: HTMLElement, tab: string) {
  return root.querySelector<HTMLElement>(`[data-record-tab="${tab}"] [data-slot="scroll-area-viewport"]`);
}

/** The reader scrolls a box; the page keeps the view once the scroll has settled, 150 ms on. */
async function scroll(element: HTMLElement | null, top: number) {
  element!.scrollTop = top;
  element!.dispatchEvent(new Event("scroll"));
  await new Promise((resolve) => setTimeout(resolve, 150));
  await settle();
}

/**
 * The view the tests leave: Details on the form's second tab with its section shut, the panel's
 * notes shut by a script's act, and all three boxes scrolled.
 */
async function leaveAView(root: HTMLElement) {
  await click(formTabButton(root, "more"));
  await click(formSectionHeader(root, "Notes"));
  await click(button(root, "Shut notes"));
  await scroll(column(root, "form"), 300);
  await scroll(column(root, "panel"), 120);
  await scroll(tabBody(root, "details"), 200);
}

function expectTheView(root: HTMLElement) {
  expect(shownTab(root)).toBe("details");
  expect(formTab(root)).toBe("more");
  expect(formSection(root, "Notes")).toBe("closed");
  expect(panelSection(root, "notes")).toBe("false");
  expect(column(root, "form")!.scrollTop).toBe(300);
  expect(column(root, "panel")!.scrollTop).toBe(120);
  expect(tabBody(root, "details")!.scrollTop).toBe(200);
}

/** The panel and the columns as a first visit draws them, then the Details form once the reader opens it. */
async function expectANewVisit(root: HTMLElement) {
  expect(panelSection(root, "notes")).toBe("true");
  expect(column(root, "form")!.scrollTop).toBe(0);
  expect(column(root, "panel")!.scrollTop).toBe(0);
  if (shownTab(root) !== "details") await click(stripButton(root, "details"));
  expect(formSection(root, "Notes")).toBe("open");
  expect(tabBody(root, "details")!.scrollTop).toBe(0);
}

/** The first visit, with the view left on it, then the list. */
async function visitLeavingAView(query = "") {
  await register({ onRefresh: notesPanel });
  const page = await mount(`/note/${name}${query}`);
  await leaveAView(page.root);
  await leave(page.router);
  return page;
}

/** Every tab body added under `root` from now on, by tab name. */
function watchTabBodies(root: HTMLElement) {
  const seen: string[] = [];
  const observer = new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.addedNodes)
        if (node instanceof HTMLElement)
          for (const element of [node, ...node.querySelectorAll<HTMLElement>("[data-record-tab]")])
            if (element.dataset.recordTab) seen.push(element.dataset.recordTab);
  });
  observer.observe(root, { childList: true, subtree: true });
  return { seen, stop: () => observer.disconnect() };
}

/** A newer list row leaves the record's entry partial, so it is no longer complete in the cache. */
function makePartial(record: string) {
  const ticket = takeTicket();
  feedListRead(ticket, "Note", {}, { data: [{ name: record, modified: NEW }] } as never);
  settleTicket(ticket);
}

describe("when the view comes back", () => {
  it("comes back on a sidebar or rail click, or a plain link to a record seen before", async () => {
    const { root, router } = await visitLeavingAView();

    await comeBack(router);
    await settle();

    expectTheView(root);
  });

  it("comes back on the tab the reader left for the list", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount(`/note/${name}`);
    await click(stripButton(root, "files"));
    await leave(router);

    await comeBack(router);
    await settle();

    expect(shownTab(root)).toBe("files");
  });

  it("comes back on Back", async () => {
    const { root, router } = await visitLeavingAView();

    await travel(router, -1);
    await settle();

    expectTheView(root);
  });

  it("comes back on Forward", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount("/note");
    await comeBack(router);
    await settle();
    await leaveAView(root);
    await travel(router, -1);
    await settle();

    await travel(router, 1);
    await settle();

    expectTheView(root);
  });

  it("does not come back on a link that names a tab", async () => {
    const { root, router } = await visitLeavingAView();

    await comeBack(router, "?tab=files");
    await settle();

    expect(shownTab(root)).toBe("files");
    await expectANewVisit(root);
  });

  it("does not come back on a link that points at an activity row", async () => {
    const { root, router } = await visitLeavingAView();

    await comeBack(router, "?activity=a1");
    await settle();

    expect(shownTab(root)).toBe("activity");
    await expectANewVisit(root);
  });
});

describe("where the view is kept", () => {
  it("takes the history entry's view over the record's own on Back", async () => {
    const { root, router } = await visitLeavingAView();
    await comeBack(router);
    await settle();
    await click(stripButton(root, "files"));
    await leave(router);

    await travel(router, -3);
    await settle();

    expectTheView(root);
  });

  it("drops the record's own view once its complete entry leaves the cache, and Back still restores", async () => {
    const { root, router } = await visitLeavingAView();
    makePartial(name);

    await comeBack(router);
    await settle();

    expect(shownTab(root)).toBe("details");
    await expectANewVisit(root);

    await leave(router);
    await travel(router, -3);
    await settle();

    expectTheView(root);
  });

  it("keeps each history entry's own offsets for a record open at two, on Back and Forward", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount(`/note/${name}`);
    await scroll(column(root, "form"), 100);
    await comeBack(router, "", other);
    await settle();
    await comeBack(router);
    await settle();
    await scroll(column(root, "form"), 300);

    await travel(router, -1);
    await settle();
    await travel(router, -1);
    await settle();
    expect(column(root, "form")!.scrollTop).toBe(100);

    await travel(router, 1);
    await settle();
    await travel(router, 1);
    await settle();
    expect(column(root, "form")!.scrollTop).toBe(300);
  });

  it("comes back on Forward from the history entry once the record's own copy is dropped", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount("/note");
    await comeBack(router);
    await settle();
    await leaveAView(root);
    await travel(router, -1);
    await settle();
    clearDataCache();

    await travel(router, 1);
    await settle();

    expectTheView(root);
  });
});

describe("a script's onOpen on a return", () => {
  function openOnActivity() {
    return register({
      onOpen: (page) => page.tabs.activate("activity"),
      onRefresh: notesPanel,
    });
  }

  it("moves the reader on a new visit", async () => {
    await openOnActivity();
    const { root } = await mount(`/note/${name}`);

    expect(shownTab(root)).toBe("activity");
  });

  it("does not move a reader whose view the page restores", async () => {
    await openOnActivity();
    const { root, router } = await mount(`/note/${name}`);
    await click(stripButton(root, "details"));
    await leave(router);

    await comeBack(router);
    await settle();

    expect(shownTab(root)).toBe("details");
  });
});

describe("when the view is set", () => {
  it("is right at the first render of a paint from memory, offsets before any frame", async () => {
    const { root, router } = await visitLeavingAView();
    vi.stubGlobal("requestAnimationFrame", () => 0);
    const drawn = watchTabBodies(root);

    await comeBack(router);
    for (let turn = 0; turn < 10; turn++) await Promise.resolve();

    drawn.stop();
    expect(drawn.seen).toEqual(["details"]);
    expectTheView(root);
  });

  it("draws only the restored tab's body on a paint from memory, at its offset before any frame", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount(`/note/${name}`);
    await click(stripButton(root, "files"));
    await scroll(tabBody(root, "files"), 250);
    await leave(router);
    vi.stubGlobal("requestAnimationFrame", () => 0);
    const drawn = watchTabBodies(root);

    await comeBack(router);
    for (let turn = 0; turn < 10; turn++) await Promise.resolve();

    drawn.stop();
    expect(drawn.seen).toEqual(["files"]);
    expect(tabBody(root, "files")!.scrollTop).toBe(250);
  });

  it("is set once the content is ready on a cold load", async () => {
    const { root, router } = await visitLeavingAView();
    clearDataCache();
    server.holdRecord = gate();

    await travel(router, -1);
    await settle();

    expect(root.querySelector("[data-record-tabs]")).toBeNull();

    server.holdRecord.open();
    await settle();

    expectTheView(root);
  });

  it("reads a restored feed tab beside the record on a cold load, under the feed's placeholder", async () => {
    // Activity is first with Details hidden, so the address never names it.
    await register({ onRefresh: (page) => page.tabs.hide("details") });
    const { root, router } = await mount(`/note/${name}`);
    expect(shownTab(root)).toBe("activity");
    await leave(router);
    clearDataCache();
    server.holdRecord = gate();
    const before = server.activityReads;

    await travel(router, -1);
    await settle();

    expect(server.activityReads - before).toBe(1);
    expect(root.querySelector("[data-feed-skeleton]")).not.toBeNull();

    server.holdRecord.open();
    await settle();

    expect(shownTab(root)).toBe("activity");
    expect(server.activityReads - before).toBe(1);
  });

  it("is not moved by the background re-read or a DocType change", async () => {
    const { root, router } = await visitLeavingAView();
    server.holdRecord = gate();
    server.doc = { ...server.doc, title: "Second", modified: NEW };
    server.meta = { ...META, fields: [...META.fields, { fieldname: "stage", fieldtype: "Data", label: "Stage" }] };
    socket.emit("doctype_update", { doctype: "Note" });
    await comeBack(router);
    await settle();
    await click(stripButton(root, "files"));
    await click(stripButton(root, "details"));
    await scroll(column(root, "form"), 40);

    server.holdRecord.open();
    await settle();

    expect(root.querySelector("[data-crumbs]")?.textContent).toContain("Second");
    expect(shownTab(root)).toBe("details");
    expect(column(root, "form")!.scrollTop).toBe(40);
    expect(tabBody(root, "details")!.scrollTop).toBe(200);
  });
});

describe("a view that no longer fits", () => {
  it("takes a new visit's tab at its top when the saved tab is gone, and still sets the columns", async () => {
    let hideFiles = false;
    await register({
      onRefresh: (page) => {
        notesPanel(page);
        if (hideFiles) page.tabs.hide("files");
      },
    });
    const { root, router } = await mount(`/note/${name}`);
    await click(stripButton(root, "files"));
    await scroll(tabBody(root, "files"), 250);
    await scroll(column(root, "form"), 300);
    await leave(router);
    hideFiles = true;

    await comeBack(router);
    await settle();

    expect(shownTab(root)).toBe("details");
    expect(tabBody(root, "details")!.scrollTop).toBe(0);
    expect(column(root, "form")!.scrollTop).toBe(300);
  });

  it("sets the offsets as saved when the content is shorter now", async () => {
    const { root, router } = await visitLeavingAView();
    box.scrollHeight = 600;

    await comeBack(router);
    for (let frame = 0; frame < 70; frame++) await new Promise((resolve) => requestAnimationFrame(resolve));
    await settle();

    expect(column(root, "form")!.scrollTop).toBe(300);
    expect(tabBody(root, "details")!.scrollTop).toBe(200);
  });
});

describe("a new navigation to another record", () => {
  it("carries none of the last record's scroll or Details sections", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount(`/note/${other}`);
    await leave(router);
    await comeBack(router);
    await settle();
    await leaveAView(root);
    const body = column(root, "form");

    await comeBack(router, "", other);
    await settle();

    expect(column(root, "form")).not.toBe(body);
    expect(formSection(root, "Notes") ?? formSection(root, "Summary")).toBe("open");
    expect(column(root, "form")!.scrollTop).toBe(0);
    expect(tabBody(root, "details")!.scrollTop).toBe(0);
  });

  it("leaves the last record's view as it was", async () => {
    await register({ onRefresh: notesPanel });
    const { root, router } = await mount(`/note/${other}`);
    await leave(router);
    await comeBack(router);
    await settle();
    await click(stripButton(root, "files"));
    await comeBack(router, "", other);
    await settle();

    await comeBack(router);
    await settle();

    expect(shownTab(root)).toBe("files");
  });
});
