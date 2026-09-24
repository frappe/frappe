// The record page while it loads: header and body skeletons until the first replay commits, and
// the panel sections' while the Side Panel layout loads.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";
import { RouterView } from "vue-router";

const load = vi.hoisted(() => ({
  answerRecord: (() => {}) as () => void,
  // Set by a test: the record read fails with it.
  failure: null as unknown,
  layouts: {} as Record<string, { loading: { value: boolean }; layout: { value: unknown[] } }>,
  scripts: Promise.resolve(),
}));

vi.mock("@/shell/PageFrame.vue", async () => {
  const { defineComponent, h } = await import("vue");
  return {
    pageGutter: "px-[--page-gutter]",
    default: defineComponent({
      setup: (_, { slots }) => () => h("div", [h("header", slots.header?.()), slots.default?.()]),
    }),
  };
});

vi.mock("../recordSource", () => ({
  loadRecord: vi.fn(
    () =>
      new Promise((resolve, reject) => {
        if (load.failure) return reject(load.failure);
        load.answerRecord = () =>
          resolve({
            document: { doctype: "Note", name: "N-1", modified: "2026-09-24 10:00:00" },
            docinfo: { permissions: { read: 1, write: 1 } },
            linkTitles: {},
          });
      }),
  ),
  loadParts: vi.fn(async () => ({})),
  saveRecord: vi.fn(),
}));

vi.mock("../metaSource", () => ({ fetchMeta: vi.fn(async () => ({ name: "Note", fields: [] })) }));

vi.mock("@/recordPage", async (importOriginal) => {
  const original = (await importOriginal()) as object;
  const { computed, ref, watch } = await import("vue");
  return {
    ...original,
    loadClientScripts: vi.fn(() => load.scripts),
    // One fake per layout type, flipped by the test: `loading` until it is told otherwise.
    useFormLayout: ({ type }: { type: string }) => {
      const state = { loading: ref(true), layout: ref<unknown[]>([]) };
      load.layouts[type] = state;
      return {
        layout: computed(() => state.layout.value),
        loading: computed(() => state.loading.value),
        error: computed(() => null),
        reload: () => {},
        settled: () =>
          new Promise<void>((resolve) => {
            if (!state.loading.value) return resolve();
            const stop = watch(state.loading, (busy) => {
              if (busy) return;
              stop();
              resolve();
            });
          }),
      };
    },
  };
});

vi.mock("@/pages/Home.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/List.vue", () => ({ default: { render: () => null } }));
vi.mock("@/pages/Module.vue", () => ({ default: { render: () => null } }));
vi.mock("@/shell/NotFound.vue", () => ({ default: { render: () => null } }));

import { ApiError } from "@framework/ui/api";
import { Addresses } from "@/addresses";
import type { Boot } from "@/boot";
import { loadClientScripts } from "@/recordPage";
import { FIRST_PAINT_LIMIT_MS } from "@/recordPage/paintGate";
import { withRegisteringSource } from "@/recordPage/context";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import { createShellRouter } from "@/router";
import { RecordFeeds } from "../feed/recordFeeds";
import { loadRecord } from "../recordSource";
import { registerShell } from "@/router/routeFor";

const boot = {
  app: "frappe",
  shell_base: "/apps/frappe",
  prefixes: { frappe: { app: "frappe", modular: false } },
  session: { user: { name: "test@example.com", email: "test@example.com" } },
} as unknown as Boot;
const addresses = new Addresses({ doctypes: { Note: ["note", "desk"] }, modules: { desk: "Desk" } });
const apps: ReturnType<typeof createApp>[] = [];

beforeEach(() => {
  vi.clearAllMocks();
  load.layouts = {};
  load.failure = null;
  load.scripts = Promise.resolve();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ data: null }), { status: 200 })),
  );
});

afterEach(() => {
  vi.useRealTimers();
  for (const app of apps.splice(0)) app.unmount();
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

async function settle() {
  for (let turn = 0; turn < 10; turn++) {
    await nextTick();
    if (vi.isFakeTimers()) await vi.advanceTimersByTimeAsync(0);
    else await new Promise((resolve) => setTimeout(resolve));
  }
}

async function open(address = "/note/N-1") {
  const router = createShellRouter(boot, addresses);
  registerShell({ boot, addresses, router });
  await router.push(address);
  const root = document.createElement("div");
  document.body.appendChild(root);
  const app = createApp(defineComponent({ render: () => h(RouterView) }));
  app.use(router);
  app.provide("boot", boot);
  app.provide("addresses", addresses);
  app.provide("socket", { emit() {}, on() {}, off() {} });
  app.mount(root);
  apps.push(app);
  await settle();
  return root;
}

async function settleLayouts() {
  load.layouts["Details"].loading.value = false;
  load.layouts["Side Panel"].loading.value = false;
  await settle();
}

function answerActivity(row: object) {
  const answer = (url: string) =>
    url.includes("/api/v2/document/Note/N-1/activity")
      ? { data: { activities: [row], next: null } }
      : { data: null };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => new Response(JSON.stringify(answer(String(url))), { status: 200 })),
  );
}

function skeletons(root: HTMLElement, hook: string) {
  return root.querySelectorAll(`[${hook}] .fui-skeleton`).length;
}

describe("before the first replay commits", () => {
  it("asks for the Client Scripts before the record read answers", async () => {
    await open();

    expect(loadRecord).toHaveBeenCalledOnce();
    expect(loadClientScripts).toHaveBeenCalledWith("Note");
  });

  it("draws the header row's skeleton in place of the crumbs, star, menu and Save", async () => {
    const root = await open();

    expect(skeletons(root, "data-record-header-skeleton")).toBe(5);
    expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);

    load.answerRecord();
    await settle();

    expect(skeletons(root, "data-record-header-skeleton")).toBe(5);

    await settleLayouts();

    expect(root.querySelector("[data-record-header-skeleton]")).toBeNull();
    expect(root.querySelector("[data-crumbs]")).not.toBeNull();
  });

  it("draws the strip, the Details form and the panel as skeletons, the panel at its width", async () => {
    const root = await open();

    const body = root.querySelector("[data-record-body-skeleton]")!;
    expect(skeletons(body as HTMLElement, "data-record-tabs-skeleton")).toBe(4);
    const form = body.querySelector("[data-form-skeleton]")!;
    expect(form.querySelectorAll(".fui-skeleton")).toHaveLength(16);
    expect(form.querySelector(".grid")!.className).toContain("sm:grid-cols-2");
    expect(skeletons(body as HTMLElement, "data-record-panel-skeleton")).toBeGreaterThan(0);
    expect(body.querySelector<HTMLElement>('[data-body-column="panel"]')!.style.width).toBe(
      "380px",
    );

    load.answerRecord();
    await settle();

    expect(root.querySelector("[data-record-body-skeleton]")).not.toBeNull();
    expect(root.querySelector("[data-record-tabs]")).toBeNull();

    await settleLayouts();

    expect(root.querySelector("[data-record-body-skeleton]")).toBeNull();
    expect(root.querySelector("[data-record-panel-skeleton]")).toBeNull();
    expect(root.querySelector("[data-record-panel]")).not.toBeNull();
  });

  it("keeps both skeletons while the Client Scripts load, and lifts them on the commit", async () => {
    // Fake timers, so the first-paint limit cannot lift the skeletons on a slow run.
    vi.useFakeTimers();
    let answerScripts = () => {};
    load.scripts = new Promise<void>((resolve) => (answerScripts = resolve));
    const root = await open();
    load.answerRecord();
    await settleLayouts();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS - 1);

    expect(root.querySelector("[data-record-header-skeleton]")).not.toBeNull();
    expect(root.querySelector("[data-record-body-skeleton]")).not.toBeNull();

    answerScripts();
    await settle();

    expect(root.querySelector("[data-record-header-skeleton]")).toBeNull();
    expect(root.querySelector("[data-record-body-skeleton]")).toBeNull();
    expect(root.querySelector("[data-crumbs]")).not.toBeNull();
    expect(root.querySelector("[data-record-tabs]")).not.toBeNull();
  });
});

describe("an address that opens a feed", () => {
  it.each(["?tab=activity", "?tab=emails", "?activity=x", "?tab=files&activity=x"])(
    "draws the feed's skeleton under the strip for %s, before and after the record arrives",
    async (query) => {
      const root = await open(`/note/N-1${query}`);

      const early = root.querySelectorAll("[data-record-body-skeleton] [data-feed-skeleton] .fui-skeleton");
      expect(early.length).toBeGreaterThan(0);
      expect(root.querySelector("[data-form-skeleton]")).toBeNull();

      load.answerRecord();
      await settle();

      const late = root.querySelectorAll("[data-record-body-skeleton] [data-feed-skeleton] .fui-skeleton");
      expect(late.length).toBeGreaterThan(0);
      expect(root.querySelector("[data-form-skeleton]")).toBeNull();
    },
  );

  it.each(["?tab=files", "?tab=details"])("draws the form's skeleton for %s", async (query) => {
    const root = await open(`/note/N-1${query}`);

    expect(root.querySelector("[data-record-body-skeleton] [data-form-skeleton]")).not.toBeNull();
    expect(root.querySelector("[data-feed-skeleton]")).toBeNull();
  });
});

describe("once the page has painted", () => {
  it("opens on the Activity tab a pointer names, and scrolls to the row", async () => {
    answerActivity({ type: "log", key: "x", data: { name: "x", subtype: "info", text: "Row x" } });
    const scroll = vi.spyOn(RecordFeeds.prototype, "scrollToActivity");
    const root = await open("/note/N-1?activity=x");
    load.answerRecord();
    await settleLayouts();

    const activity = root.querySelector<HTMLElement>('[data-record-tab="activity"]');
    expect(activity!.style.display).toBe("");
    expect(root.querySelector('[data-record-tab="details"]')).toBeNull();
    expect(scroll).toHaveBeenCalledWith("x");
    expect(activity!.querySelector('.activity[id="x"]')!.textContent).toContain("Row x");
    scroll.mockRestore();
  });

  it("draws the panel sections skeleton while the Side Panel layout reloads", async () => {
    const root = await open();
    load.answerRecord();
    await settleLayouts();

    expect(root.querySelector("[data-panel-sections-skeleton]")).toBeNull();

    load.layouts["Side Panel"].loading.value = true;
    await settle();

    expect(skeletons(root, "data-panel-sections-skeleton")).toBeGreaterThan(0);

    load.layouts["Side Panel"].loading.value = false;
    await settle();

    expect(root.querySelector("[data-panel-sections-skeleton]")).toBeNull();
    expect(root.querySelector("[data-record-panel]")).not.toBeNull();
  });
});

describe("when the record read fails", () => {
  it.each([
    [404, "Not found."],
    [403, "You do not have permission to read this record."],
  ])("drops the skeletons for the plain heading and the error on a %i", async (status, text) => {
    load.failure = new ApiError({ type: "Error", message: "no" } as never, status);

    const root = await open();

    expect(root.querySelector("h1")!.textContent).toBe("N-1");
    expect(root.textContent).toContain(text);
    expect(root.querySelector("[data-record-header-skeleton]")).toBeNull();
    expect(root.querySelector("[data-record-body-skeleton]")).toBeNull();
  });
});

describe("a header or quick action's run paints once", () => {
  afterEach(() => resetRegistry());

  function labels(root: HTMLElement) {
    return [...root.querySelectorAll("button")].map((button) => button.textContent!.trim());
  }

  it("draws what run adds on both sides of an await together, when run finishes", async () => {
    let root!: HTMLElement;
    let midway: string[] = [];
    let finish = () => {};
    const finished = new Promise<void>((resolve) => (finish = resolve));
    await withRegisteringSource("paint-once", async () =>
      registerRecordPage("Note", {
        onRefresh: (page) =>
          page.quickActions.add({
            name: "twice",
            label: "Add twice",
            run: async (page) => {
              page.quickActions.add({ name: "a", label: "A" });
              await nextTick();
              await Promise.resolve();
              midway = labels(root);
              page.quickActions.add({ name: "b", label: "B" });
              finish();
            },
          }),
      }),
    );
    root = await open();
    load.answerRecord();
    await settleLayouts();

    [...root.querySelectorAll("button")].find((one) => one.textContent!.trim() === "Add twice")!.click();
    await finished;
    await settle();

    expect(midway).toContain("Add twice");
    expect(midway).not.toContain("A");
    expect(midway).not.toContain("B");
    expect(labels(root)).toEqual(expect.arrayContaining(["Add twice", "A", "B"]));
  });
});
