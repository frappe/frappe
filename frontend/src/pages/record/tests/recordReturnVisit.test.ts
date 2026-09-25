// A return visit paints from the shared cache before the first frame, then one quiet re-read and one replay.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView, type Router } from "vue-router";

const load = vi.hoisted(() => ({ layoutsLoading: false, failFirstReplay: false }));
const prefetchEnded = vi.hoisted(() => [] as string[]);

vi.mock("@framework/ui/ActivityTimeline", async (importOriginal) => {
  const original = (await importOriginal()) as typeof import("@framework/ui/ActivityTimeline");
  return {
    ...original,
    endActivityPrefetch: (doctype: string, docname: string, ...rest: []) => {
      prefetchEnded.push(docname);
      return original.endActivityPrefetch(doctype, docname, ...rest);
    },
  };
});

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
    }),
  };
});

vi.mock("@/recordPage", async (importOriginal) => {
  const original = (await importOriginal()) as object;
  const { computed, ref } = await import("vue");
  return {
    ...original,
    createRecordPage: (...args: unknown[]) => {
      const created = (original as any).createRecordPage(...args);
      if (!load.failFirstReplay) return created;
      created.paintNow = () => null;
      created.refresh = () => Promise.reject(new Error("replay failed"));
      return created;
    },
    useFormLayout: () => {
      const loading = ref(load.layoutsLoading);
      return {
        layout: computed(() => []),
        loading: computed(() => loading.value),
        error: computed(() => null),
        reload: () => {},
        settled: async () => {},
      };
    },
  };
});

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { activityTimelineRows } from "@framework/ui/ActivityTimeline";
import { clearDataCache, feedListRead, settleTicket, takeTicket } from "@framework/ui/cache";
import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { resetUserRoles, useUserRoles } from "@framework/ui/composables/useUserRoles";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { resetClientScripts } from "@/recordPage/clientScripts";
import { withRegisteringSource } from "@/recordPage/context";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import type { AuthoredHandlers, RecordPageApi } from "@/recordPage/types";
import { createShellRouter } from "@/router";
import { registerShell } from "@/router/routeFor";

const EARLIER = "2026-09-25 09:00:00.000000";
const OLD = "2026-09-25 10:00:00.000000";
const NEW = "2026-09-25 11:00:00.000000";
const SAVED = "2026-09-25 12:00:00.000000";
const META = {
  name: "Note",
  title_field: "title",
  fields: [
    { fieldname: "title", fieldtype: "Data", label: "Title" },
    { fieldname: "status", fieldtype: "Data", label: "Status" },
  ],
};

interface Gate {
  opened: Promise<void>;
  open: () => void;
}

function gate(): Gate {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

/** What the server holds and how it answers; a test moves it between visits. */
const server = {
  doc: {} as Record<string, any>,
  /** Records other than the one a test visits, by name. */
  others: {} as Record<string, Record<string, any>>,
  activity: [] as object[],
  attachments: [] as object[],
  favourites: [] as object[],
  failRecord: false,
  holdRecord: null as Gate | null,
  holdActivity: null as Gate | null,
  holdSession: null as Gate | null,
  /** One gate per docinfo re-read (a read without `seen`), taken in the order the reads start. */
  holdParts: [] as Gate[],
  requests: [] as string[],
};

async function answer(url: URL, method: string, body: any): Promise<[unknown, number]> {
  const path = decodeURIComponent(url.pathname);
  if (path === "/api/v2/doctype/Note/meta") return [{ data: META }, 200];
  if (path === "/api/v2/session") {
    await server.holdSession?.opened;
    return [{ data: null }, 200];
  }
  if (path.endsWith("/activity")) {
    await server.holdActivity?.opened;
    return [{ data: { activities: server.activity, next: null } }, 200];
  }
  if (path.endsWith("/favourites") && method === "POST") {
    server.favourites = [{ user: boot.session.user.name }];
    return [{ data: { favourites: server.favourites, users: {} } }, 200];
  }
  if (path.startsWith("/api/v2/document/Note/") && method === "PATCH") {
    server.doc = { ...server.doc, ...body, modified: SAVED };
    return [{ data: server.doc }, 200];
  }
  if (path.startsWith("/api/v2/document/Note/") && method === "GET") {
    await server.holdRecord?.opened;
    if (!url.searchParams.get("include")?.includes("seen")) await server.holdParts.shift()?.opened;
    if (server.failRecord) return [{ errors: [{ type: "Error", message: "down" }] }, 500];
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
    favourites: server.favourites,
    follows: false,
    users: {},
    link_titles: {},
    attachments: server.attachments,
    seen: [],
  };
}

function fileRow(name: string, creation: string) {
  return { name, file_name: `${name}.txt`, file_url: `/files/${name}.txt`, is_private: 0, creation, owner: "test@example.com" };
}

/** The realtime socket the page listens on; `emit` plays a server event to every listener. */
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

function activityRow(key: string, text: string) {
  return { type: "log", key, timestamp: "2026-09-25 09:00:00", data: { name: key, subtype: "info", text } };
}

const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  session: { user: { name: "test@example.com", email: "test@example.com" } },
} as unknown as Boot;
const addresses = new Addresses({ doctypes: { Note: ["note", "desk"] }, modules: { desk: "Desk" } });
const apps: ReturnType<typeof createApp>[] = [];
let warnings: string[];
let visits = 0;
let name = "";

beforeEach(() => {
  name = `N-${++visits}`;
  server.doc = { doctype: "Note", name, title: "First", status: "Open", modified: OLD };
  server.others = {};
  server.activity = [activityRow("a1", "Row one")];
  server.attachments = [];
  server.favourites = [];
  socket.handlers = {};
  server.failRecord = false;
  server.holdRecord = null;
  server.holdActivity = null;
  server.holdSession = null;
  server.holdParts = [];
  server.requests = [];
  load.layoutsLoading = false;
  load.failFirstReplay = false;
  prefetchEnded.length = 0;
  resetClientScripts();
  resetDoctypeMeta();
  resetUserRoles();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      const method = init?.method ?? "GET";
      server.requests.push(`${method} ${decodeURIComponent(url.pathname)}`);
      const sent = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
      const [body, status] = await answer(url, method, sent);
      return new Response(JSON.stringify(body), { status });
    }),
  );
});

afterEach(() => {
  for (const app of apps.splice(0)) app.unmount();
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

/** A cold first visit, settled, then the list: the record, its meta and scripts stay in memory. */
async function visitAndLeave(query = "") {
  const page = await mount(`/note/${name}${query}`);
  await settle();
  await page.router.push("/note");
  await settle();
  return page;
}

/** Back to the record; resolves once the new page has rendered once, with no timer run. */
async function comeBack(router: Router, query = "") {
  await router.push(`/note/${name}${query}`);
  await nextTick();
}

function register(handlers: AuthoredHandlers) {
  return withRegisteringSource("return-visit", async () => registerRecordPage("Note", handlers));
}

/** Draws the doc and the saved `modified` as the replay saw them, as a quick action's label. */
function drawState(page: RecordPageApi) {
  const { status, title, modified } = page.doc;
  const rows = page.activity.items.length;
  page.quickActions.add({ name: "state", label: `${status}|${title}|${modified}|${page.saved.modified}|${rows}` });
}

function state(root: HTMLElement) {
  const button = [...root.querySelectorAll("button")].find((one) => one.textContent!.includes("|"));
  return button?.textContent!.trim() ?? null;
}

function crumbs(root: HTMLElement) {
  return root.querySelector("[data-crumbs]")?.textContent ?? "";
}

function hasSkeleton(root: HTMLElement) {
  return Boolean(root.querySelector("[data-record-header-skeleton], [data-record-body-skeleton]"));
}

function click(root: HTMLElement, label: string) {
  [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === label)!.click();
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

function recordReads() {
  return server.requests.filter((request) => request === `GET /api/v2/document/Note/${name}`).length;
}

function activityReads() {
  return server.requests.filter((request) => request.endsWith(`/${name}/activity`)).length;
}

describe("a return visit", () => {
  it("draws the page from memory at its first render, with no skeleton at any point", async () => {
    const onRefresh = vi.fn(drawState);
    await register({ onRefresh });
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    const skeletons = watchSkeletons(root);
    onRefresh.mockClear();

    await comeBack(router);

    expect(hasSkeleton(root)).toBe(false);
    expect(crumbs(root)).toContain("First");
    expect(state(root)).toBe(`Open|First|${OLD}|${OLD}|0`);
    expect(onRefresh).toHaveBeenCalledOnce();

    server.holdRecord.open();
    await settle();

    expect(skeletons.seen).toEqual([]);
    skeletons.stop();
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(recordReads()).toBe(2);
  });

  it("draws nothing after the re-read when the record has not changed", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    const changes: MutationRecord[] = [];
    const observer = new MutationObserver((records) => changes.push(...records));
    observer.observe(root, { childList: true, subtree: true, characterData: true, attributes: true });

    server.holdRecord.open();
    await settle();

    observer.disconnect();
    expect(changes).toEqual([]);
    expect(recordReads()).toBe(2);
  });

  it("draws a changed value and what a script builds from it in the same task", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    server.doc = { ...server.doc, title: "Second", status: "Won", modified: NEW };

    server.holdRecord.open();
    const seen: string[] = [];
    for (let task = 0; task < 20; task++) {
      await new Promise((resolve) => setTimeout(resolve));
      seen.push(`${crumbs(root).includes("Second") ? "new" : "old"} ${state(root)}`);
    }

    expect(seen).toContain(`new Won|Second|${NEW}|${NEW}|0`);
    expect(seen.filter((one) => one.startsWith("new")).every((one) => one.includes("Won|Second"))).toBe(true);
    expect(seen.filter((one) => one.startsWith("old")).every((one) => one.includes("Open|First"))).toBe(true);
  });

  it("lands an act in the first replay, and drops one in the replay after the re-read with a warning", async () => {
    await register({
      onRefresh: (page) => {
        if (page.doc.status === "Won") page.tabs.activate("activity");
        if (page.doc.title === "Second") page.tabs.activate("files");
      },
    });
    server.doc.status = "Won";
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    await comeBack(router);
    await settle();

    expect(activeTab(root)).toBe("activity");

    server.doc = { ...server.doc, title: "Second", modified: NEW };
    server.holdRecord.open();
    await settle();

    expect(activeTab(root)).toBe("activity");
    expect(warnings).toContainEqual(expect.stringContaining('page.tabs.activate("files")'));
    expect(warnings).toContainEqual(expect.stringContaining("it ran in the replay after a background read"));
  });

  it("fires no field handler for a value the re-read changes", async () => {
    const title = vi.fn();
    const status = vi.fn();
    await register({ onRefresh: drawState, title, status });
    const { root, router } = await visitAndLeave();
    server.doc = { ...server.doc, title: "Second", status: "Won", modified: NEW };

    await comeBack(router);
    await settle();

    expect(state(root)).toBe(`Won|Second|${NEW}|${NEW}|0`);
    expect(title).not.toHaveBeenCalled();
    expect(status).not.toHaveBeenCalled();
  });

  it("lands an act a slow first replay makes after the reads returned, and replays once after it", async () => {
    const pause = gate();
    const runs = vi.fn();
    let slow = false;
    await register({
      onRefresh: async (page) => {
        runs();
        page.quickActions.add({ name: "slow", label: "Slow" });
        if (!slow) return;
        slow = false;
        await pause.opened;
        page.tabs.activate("files");
      },
    });
    const { root, router } = await visitAndLeave();
    runs.mockClear();
    slow = true;
    await comeBack(router);
    await settle();

    expect(runs).toHaveBeenCalledOnce();

    pause.open();
    await settle();

    expect(activeTab(root)).toBe("files");
    expect(buttons(root, "Slow")).toBe(1);
    expect(runs).toHaveBeenCalledTimes(2);
  });

  it("keeps a favourite the reader set while the background read was out", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    root.querySelector<HTMLElement>("[data-favourite]")!.click();
    await settle();

    expect(favourited(root)).toBe("true");

    server.holdRecord.open();
    await settle();

    expect(favourited(root)).toBe("true");
  });

  it("reads the sidecar again when a live update replaced it while the background read was out", async () => {
    const seen: string[][] = [];
    await register({
      onRefresh: (page) =>
        page.quickActions.add({
          name: "files",
          label: "List files",
          run: (page) => void seen.push(page.files.items.map((one) => one.name)),
        }),
    });
    const { root, router } = await visitAndLeave();
    server.attachments = [fileRow("F2", EARLIER)];
    server.holdRecord = gate();
    const before = recordReads();
    await comeBack(router);
    await settle();
    const added = fileRow("F1", OLD);
    server.attachments = [...server.attachments, added];
    const doc = { ...added, reference_doctype: "Note", reference_name: name };
    socket.emit("docinfo_update", { key: "attachments", action: "add", doc });
    await settle();

    server.holdRecord.open();
    await settle();
    click(root, "List files");
    await settle();

    expect(seen.at(-1)).toEqual(["F2", "F1"]);
    expect(recordReads() - before).toBe(2);
  });

  it("replays after the sidecar's re-read when a live update replaced it while the background read was out", async () => {
    const replays: string[][] = [];
    await register({ onRefresh: (page) => void replays.push(page.files.items.map((one) => one.name)) });
    const { router } = await visitAndLeave();
    server.attachments = [fileRow("F2", EARLIER)];
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    const added = fileRow("F1", OLD);
    server.attachments = [...server.attachments, added];
    const doc = { ...added, reference_doctype: "Note", reference_name: name };
    socket.emit("docinfo_update", { key: "attachments", action: "add", doc });
    await settle();
    server.attachments = [...server.attachments, fileRow("F3", NEW)];
    replays.length = 0;

    server.holdRecord.open();
    await settle();

    expect(replays).toEqual([["F2", "F1", "F3"]]);
  });

  it("replays after the newest sidecar re-read when a later re-read replaced the one the record read started", async () => {
    const replays: string[][] = [];
    await register({ onRefresh: (page) => void replays.push(page.files.items.map((one) => one.name)) });
    const { router } = await visitAndLeave();
    server.attachments = [fileRow("F2", EARLIER)];
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    const added = fileRow("F1", OLD);
    const doc = { ...added, reference_doctype: "Note", reference_name: name };
    socket.emit("docinfo_update", { key: "attachments", action: "add", doc });
    const [replaced, newest] = (server.holdParts = [gate(), gate()]);
    server.holdRecord.open();
    await settle();
    socket.emit("disconnect");
    socket.emit("connect");
    await settle();
    replays.length = 0;

    server.attachments = [fileRow("F2", EARLIER), added];
    replaced.open();
    await settle();
    server.attachments = [...server.attachments, fileRow("F3", NEW)];
    newest.open();
    await settle();

    expect(replays).toEqual([["F2", "F1", "F3"]]);
  });

  it("applies nothing from a background read that lands after the reader moved to another record", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    const late = (server.holdRecord = gate());
    await comeBack(router);
    await settle();
    server.holdRecord = null;
    server.doc = { ...server.doc, title: "Second", status: "Won", modified: NEW };
    const other = `${name}-other`;
    server.others[other] = { doctype: "Note", name: other, title: "Other", status: "Draft", modified: EARLIER };
    await router.push(`/note/${other}`);
    await settle();

    expect(state(root)).toBe(`Draft|Other|${EARLIER}|${EARLIER}|0`);

    late.open();
    await settle();

    expect(state(root)).toBe(`Draft|Other|${EARLIER}|${EARLIER}|0`);
    expect(crumbs(root)).toContain("Other");
  });

  it("keeps a save that landed while the background read was out", async () => {
    await register({
      onRefresh: (page) => {
        drawState(page);
        page.quickActions.add({
          name: "save-mine",
          label: "Save mine",
          run: async (page) => {
            page.doc.title = "Mine";
            await page.save();
          },
        });
      },
    });
    const { root, router } = await visitAndLeave();
    const late = (server.holdRecord = gate());
    const unsaved = { ...server.doc };
    await comeBack(router);
    await settle();
    server.holdRecord = null;
    click(root, "Save mine");
    await settle();

    expect(state(root)).toBe(`Open|Mine|${SAVED}|${SAVED}|0`);

    // The read held back was answered before the save reached the server.
    server.doc = unsaved;
    late.open();
    await settle();

    expect(state(root)).toBe(`Open|Mine|${SAVED}|${SAVED}|0`);
  });
});

function buttons(root: HTMLElement, label: string) {
  return [...root.querySelectorAll("button")].filter((one) => one.textContent!.trim() === label).length;
}

function favourited(root: HTMLElement) {
  return root.querySelector("[data-favourite]")?.getAttribute("aria-pressed") ?? null;
}

function activeTab(root: HTMLElement) {
  const shown = [...root.querySelectorAll<HTMLElement>("[data-record-tab]")].find((tab) => tab.style.display !== "none");
  return shown?.dataset.recordTab ?? null;
}

describe("a re-read that lands on an edited page", () => {
  async function editTitle() {
    await register({
      onRefresh: (page) => {
        drawState(page);
        page.quickActions.add({ name: "edit", label: "Edit title", run: (page) => void (page.doc.title = "Mine") });
      },
    });
    const { root, router } = await visitAndLeave();
    server.holdRecord = gate();
    await comeBack(router);
    await settle();
    click(root, "Edit title");
    await settle();
    expect(crumbs(root)).toContain("Mine");
    return root;
  }

  it("brings in the fields the reader did not touch and keeps the one they did", async () => {
    const root = await editTitle();

    server.doc = { ...server.doc, status: "Won", modified: NEW };
    server.holdRecord!.open();
    await settle();

    expect(state(root)).toBe(`Won|Mine|${NEW}|${NEW}|0`);
    expect(crumbs(root)).toContain("Mine");
  });

  it("keeps the old modified when the server changed a field the reader touched", async () => {
    const root = await editTitle();

    server.doc = { ...server.doc, title: "Theirs", status: "Won", modified: NEW };
    server.holdRecord!.open();
    await settle();

    expect(state(root)).toBe(`Won|Mine|${OLD}|${OLD}|0`);
  });
});

describe("a failed re-read", () => {
  it("keeps the record it had while the feed's re-read still applies", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave("?tab=activity");
    server.failRecord = true;
    server.doc = { ...server.doc, status: "Won", modified: NEW };
    server.activity = [activityRow("a1", "Row one"), activityRow("a2", "Row two")];

    await comeBack(router, "?tab=activity");
    await settle();

    expect(state(root)).toBe(`Open|First|${OLD}|${OLD}|2`);
    expect(root.querySelector('.activity[id="a2"]')).not.toBeNull();
  });
});

describe("the cold path", () => {
  it("is taken on a first visit, with the skeletons until the record answers", async () => {
    const onRefresh = vi.fn(drawState);
    await register({ onRefresh });
    server.holdRecord = gate();
    const { root } = await mount(`/note/${name}`);
    await settle();

    expect(hasSkeleton(root)).toBe(true);

    server.holdRecord.open();
    await settle();

    expect(hasSkeleton(root)).toBe(false);
    expect(onRefresh).toHaveBeenCalledOnce();
    expect(recordReads()).toBe(1);
  });

  it("is taken when a newer list row left the cached record partial", async () => {
    const onRefresh = vi.fn(drawState);
    await register({ onRefresh });
    const { root, router } = await visitAndLeave();
    const ticket = takeTicket();
    feedListRead(ticket, "Note", {}, { data: [{ name, modified: NEW }] } as never);
    settleTicket(ticket);
    server.holdRecord = gate();
    onRefresh.mockClear();

    await comeBack(router);
    await settle();

    expect(hasSkeleton(root)).toBe(true);

    server.holdRecord.open();
    await settle();

    expect(hasSkeleton(root)).toBe(false);
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("is taken while a form layout still loads", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    load.layoutsLoading = true;

    await comeBack(router);

    expect(hasSkeleton(root)).toBe(true);
  });

  it("is taken while the session's roles still load", async () => {
    const onRefresh = vi.fn(drawState);
    await register({ onRefresh });
    const { root, router } = await visitAndLeave();
    server.holdSession = gate();
    useUserRoles().reload();
    onRefresh.mockClear();

    await comeBack(router);
    await settle();

    expect(hasSkeleton(root)).toBe(true);
    expect(onRefresh).not.toHaveBeenCalled();

    server.holdSession.open();
    await settle();

    expect(hasSkeleton(root)).toBe(false);
    expect(onRefresh).toHaveBeenCalledOnce();
  });

  it("is taken by page.reload(), which blanks the page and reads the record again", async () => {
    await register({
      onRefresh: (page) =>
        page.quickActions.add({ name: "reload", label: "Reload", run: (page) => void page.reload() }),
    });
    const { root, router } = await visitAndLeave();
    await comeBack(router);
    await settle();
    server.holdRecord = gate();

    click(root, "Reload");
    await nextTick();

    expect(hasSkeleton(root)).toBe(true);

    server.holdRecord.open();
    await settle();

    expect(hasSkeleton(root)).toBe(false);
    expect(recordReads()).toBe(3);
  });
});

describe("a return visit on the Activity tab", () => {
  it("draws the kept rows at once and reads the feed once, even after the body mounts", async () => {
    const onRefresh = vi.fn(drawState);
    await register({ onRefresh });
    const { root, router } = await visitAndLeave("?tab=activity");
    server.holdActivity = gate();
    server.activity = [activityRow("a1", "Row one"), activityRow("a2", "Row two")];
    const before = activityReads();
    onRefresh.mockClear();

    await comeBack(router, "?tab=activity");

    expect(hasSkeleton(root)).toBe(false);
    expect(state(root)).toBe(`Open|First|${OLD}|${OLD}|1`);
    expect(onRefresh).toHaveBeenCalledOnce();

    await settle();
    server.holdActivity.open();
    await new Promise((resolve) => setTimeout(resolve, 400));
    await settle();

    expect(root.querySelector('.activity[id="a2"]')).not.toBeNull();
    expect(state(root)).toBe(`Open|First|${OLD}|${OLD}|2`);
    expect(onRefresh).toHaveBeenCalledTimes(2);
    expect(activityReads() - before).toBe(1);
  });

  it("holds the re-read rows back until the record's read returns, then draws both in one task", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave("?tab=activity");
    server.holdRecord = gate();
    server.activity = [activityRow("a1", "Row one"), activityRow("a2", "Row two")];

    await comeBack(router, "?tab=activity");
    await settle();

    expect(root.querySelector('.activity[id="a2"]')).toBeNull();

    server.doc = { ...server.doc, title: "Second", modified: NEW };
    server.holdRecord.open();
    const seen: string[] = [];
    for (let task = 0; task < 20; task++) {
      await new Promise((resolve) => setTimeout(resolve));
      const rows = root.querySelector('.activity[id="a2"]') ? "rows" : "no rows";
      seen.push(`${rows} ${crumbs(root).includes("Second") ? "new" : "old"}`);
    }

    expect(seen).toContain("rows new");
    expect(seen.every((one) => one === "rows new" || one === "no rows old")).toBe(true);
  });

  it("reads the feed once on a return visit to Activity", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave("?tab=activity");
    const before = activityReads();

    await comeBack(router, "?tab=activity");
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 400));
    await settle();

    expect(activeTab(root)).toBe("activity");
    expect(activityReads() - before).toBe(1);
  });

  it("catches up when the reader opens Activity after a return visit on Details has applied its reads", async () => {
    await register({
      onRefresh: (page) =>
        page.quickActions.add({ name: "open", label: "Open Activity", run: (page) => page.tabs.activate("activity") }),
    });
    const { root, router } = await visitAndLeave("?tab=activity");
    const before = activityReads();
    await comeBack(router);
    await settle();

    expect(activeTab(root)).not.toBe("activity");
    expect(activityReads() - before).toBe(1);

    server.activity = [activityRow("a1", "Row one"), activityRow("a2", "Row two")];
    click(root, "Open Activity");
    await settle();
    await new Promise((resolve) => setTimeout(resolve, 400));
    await settle();

    expect(activeTab(root)).toBe("activity");
    expect(activityReads() - before).toBe(2);
    expect(root.querySelector('.activity[id="a2"]')).not.toBeNull();
  });

  it("ends the kept feed's mark when the first replay fails, and handles a failed background read", async () => {
    await register({ onRefresh: drawState });
    const { router } = await visitAndLeave("?tab=activity");
    const errors: unknown[] = [];
    apps.at(-1)!.config.errorHandler = (error) => void errors.push(error);
    server.failRecord = true;
    load.failFirstReplay = true;
    prefetchEnded.length = 0;

    await comeBack(router);
    await settle();

    expect(errors).toEqual([expect.objectContaining({ message: "replay failed" })]);
    expect(prefetchEnded).toContain(name);
  });

  it("applies the kept feed's re-read before ending its mark when the first replay fails", async () => {
    await register({ onRefresh: drawState });
    const { router } = await visitAndLeave("?tab=activity");
    apps.at(-1)!.config.errorHandler = () => {};
    server.activity = [activityRow("a1", "Row one"), activityRow("a2", "Row two")];
    server.holdActivity = gate();
    load.failFirstReplay = true;

    await comeBack(router);
    await settle();
    prefetchEnded.length = 0;
    server.holdActivity.open();
    await settle();

    expect(prefetchEnded).toContain(name);
    expect(activityTimelineRows("Note", name).map((row: any) => row.key)).toContain("a2");
  });

  it("takes the cold path when no past visit kept the feed", async () => {
    await register({ onRefresh: drawState });
    const { root, router } = await visitAndLeave();
    server.holdActivity = gate();

    await comeBack(router, "?tab=activity");
    await settle();

    expect(hasSkeleton(root)).toBe(true);

    server.holdActivity.open();
    await settle();

    expect(hasSkeleton(root)).toBe(false);
  });
});
