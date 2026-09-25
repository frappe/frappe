// A return visit: the replay from memory commits before `paintNow` returns; the next draws only changes.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watchEffect } from "vue";

const scripts = vi.hoisted(() => ({ list: null as Promise<unknown> | null }));

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({
    data: null,
    loading: false,
    fetch() {},
    reload() {},
  }),
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", async () => {
  const { GET_CLIENT_SCRIPTS } = await import("../clientScriptTypes");
  return {
    runMethod: vi.fn(async (method: string) =>
      method === GET_CLIENT_SCRIPTS ? scripts.list : { data: null },
    ),
    getMeta: vi.fn(async () => ({ data: null })),
  };
});

import { resetDoctypeMeta } from "@framework/ui/composables/useDoctypeMeta";
import { loadClientScripts, resetClientScripts } from "../clientScripts";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { withRegisteringSource } from "../context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

const RECORD_TABS = [
  { name: "details", label: "Details" },
  { name: "notes", label: "Notes" },
];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const moved: string[] = [];
  const doc = ref<Record<string, any>>({ status: "Open" });
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc,
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "details",
    activateTab: (tab) => void moved.push(tab),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    sourcesReady: () => loadClientScripts("CRM Deal"),
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
  return { controller, moved, doc };
}

/** A page whose scripts and permissions are in, as on a return visit. */
async function loadedPage() {
  await loadClientScripts("CRM Deal");
  const made = makePage();
  await vi.advanceTimersByTimeAsync(0);
  return made;
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage("CRM Deal", handlers));
}

// One function for every action, so an unchanged replay builds equal ops.
const run = () => {};

function action(name: string, label = name) {
  return { name, label, run };
}

const drawn = (controller: ReturnType<typeof makePage>["controller"]) =>
  controller.quickActions.visible().map((one) => one.label);

function countPaints(controller: ReturnType<typeof makePage>["controller"]) {
  const paints = { actions: -1, fields: -1 };
  const count = (key: keyof typeof paints, read: () => unknown) =>
    watchEffect(
      () => {
        read();
        paints[key] += 1;
      },
      { flush: "sync" },
    );
  count("actions", () => controller.quickActions.resolve());
  count("fields", () => controller.fields.resolve());
  return paints;
}

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetClientScripts();
  scripts.list = Promise.resolve({ data: { scripts: [], can_write: false } });
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("paintNow", () => {
  it("has committed the replay, landed its acts and lifted the skeletons when it returns", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        page.tabs.activate("notes");
      },
    });
    await register("later", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("two")),
    });
    const { controller, moved } = await loadedPage();

    expect(controller.paintNow()).toBe(true);

    expect(controller.ready.value).toBe(true);
    expect(controller.isReplaying.value).toBe(false);
    expect(drawn(controller)).toEqual(["one", "two"]);
    expect(moved).toEqual(["notes"]);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("opens and commits in one step, before any microtask runs", async () => {
    const seen: boolean[] = [];
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        queueMicrotask(() => void seen.push(controller.isReplaying.value));
      },
    });
    const { controller } = await loadedPage();
    const paints = countPaints(controller);

    controller.paintNow();

    expect(paints.actions).toBe(1);
    await vi.advanceTimersByTimeAsync(0);
    expect(seen).toEqual([false]);
  });

  it("warns about an onRefresh that returns a promise, and ignores what it does after its await", async () => {
    const pause = gate();
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
    });
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        page.quickActions.add(action("two"));
        await pause.opened;
        page.quickActions.add(action("three"));
        page.fields.hide("rate");
        page.tabs.activate("notes");
      },
    });
    await register("after", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("four")),
    });
    const { controller, moved } = await loadedPage();

    expect(controller.paintNow()).toBe(true);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one", "two", "four"]);
    expect(warnings).toEqual([
      "[record-page] slow.onRefresh on CRM Deal returned a promise, which is not awaited; onRefresh is synchronous.",
    ]);

    const held = gate();
    const holding = controller.hold(() => held.opened);
    pause.open();
    await vi.advanceTimersByTimeAsync(0);
    held.open();
    await holding;
    await controller.refresh();

    expect(drawn(controller)).toEqual(["one", "two", "four"]);
    expect(controller.fields.resolve()).toEqual({});
    expect(moved).toEqual([]);
  });

  it("does nothing and answers false while the doctype's scripts are loading", async () => {
    scripts.list = new Promise<never>(() => {});
    const onRefresh = vi.fn((page: RecordPageApi) => page.quickActions.add(action("one")));
    await register("deal", { onRefresh });
    void loadClientScripts("CRM Deal");
    const { controller } = makePage();
    await vi.advanceTimersByTimeAsync(0);

    expect(controller.paintNow()).toBe(false);

    expect(onRefresh).not.toHaveBeenCalled();
    expect(controller.ready.value).toBe(false);
    expect(controller.isReplaying.value).toBe(false);
    expect(drawn(controller)).toEqual([]);
  });

  it("answers false when the doctype's scripts were never asked for", async () => {
    const { controller } = makePage();
    await vi.advanceTimersByTimeAsync(0);

    expect(controller.paintNow()).toBe(false);
    expect(controller.ready.value).toBe(false);
  });

  it("answers false while the page's permissions are loading", async () => {
    resetDoctypeMeta();
    await loadClientScripts("CRM Deal");
    const onRefresh = vi.fn();
    await register("deal", { onRefresh });
    const { controller } = makePage();

    expect(controller.paintNow()).toBe(false);
    expect(onRefresh).not.toHaveBeenCalled();
  });
});

describe("refresh({ background: true })", () => {
  it("drops the replay's acts with a warning and fires no field handler", async () => {
    const status = vi.fn();
    await register("deal", {
      onRefresh: (page: RecordPageApi) => page.tabs.activate("notes"),
      status,
    });
    const { controller, moved, doc } = await loadedPage();
    controller.paintNow();
    expect(moved).toEqual(["notes"]);

    doc.value.status = "Won";
    await controller.refresh({ background: true });

    expect(moved).toEqual(["notes"]);
    expect(status).not.toHaveBeenCalled();
    expect(warnings).toEqual([
      '[record-page] page.tabs.activate("notes") — it ran in the replay after a background read; the reader was not moved.',
    ]);

    await controller.refresh();
    expect(moved).toEqual(["notes", "notes"]);
  });

  it("draws nothing when the replay's ops have not changed", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("status", page.doc.status));
        page.fields.hide("rate");
      },
    });
    const { controller } = await loadedPage();
    controller.paintNow();
    const paints = countPaints(controller);

    await controller.refresh({ background: true });

    expect(paints).toEqual({ actions: 0, fields: 0 });
    expect(drawn(controller)).toEqual(["Open"]);
  });

  it("opens and commits in one step once the sources are in", async () => {
    const seen: boolean[] = [];
    let status = "Open";
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("status", status));
        queueMicrotask(() => void seen.push(controller.isReplaying.value));
      },
    });
    const { controller } = await loadedPage();
    controller.paintNow();
    await vi.advanceTimersByTimeAsync(0);
    seen.length = 0;
    const paints = countPaints(controller);

    status = "Won";
    await controller.refresh({ background: true });

    expect(seen).toEqual([false]);
    expect(paints.actions).toBe(1);
    expect(drawn(controller)).toEqual(["Won"]);
  });

  it("keeps its newer ops when a hold open across it commits", async () => {
    let status = "Open";
    await register("deal", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("status", status)),
    });
    const { controller } = await loadedPage();
    controller.paintNow();
    const pause = gate();
    const held = controller.hold(async () => {
      await pause.opened;
      controller.page.quickActions.add(action("held"));
    });

    status = "Won";
    await controller.refresh({ background: true });
    pause.open();
    await held;

    expect(drawn(controller)).toEqual(["Won", "held"]);
  });

  it("draws an action whose function is new, so a click never runs the last replay's", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) =>
        page.quickActions.add({ name: "status", label: "Status", run: () => {} }),
    });
    const { controller } = await loadedPage();
    controller.paintNow();
    const paints = countPaints(controller);

    await controller.refresh({ background: true });

    expect(paints.actions).toBe(1);
  });

  it("lands an act a hold made before an overlapping background replay opened", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
    });
    const { controller, moved } = await loadedPage();
    controller.paintNow();
    const pause = gate();
    const held = controller.hold(async () => {
      controller.page.tabs.activate("notes");
      await pause.opened;
    });

    await controller.refresh({ background: true });
    expect(moved).toEqual([]);
    pause.open();
    await held;

    expect(moved).toEqual(["notes"]);
    expect(warnings).toEqual([]);
  });

  it("draws nothing when an unchanged replay hands one new object to two ops", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        const create = { label: "New", icon: "lucide-plus", run };
        page.tabs.add([
          { name: "one", label: "One", create },
          { name: "two", label: "Two", create },
        ]);
      },
    });
    const { controller } = await loadedPage();
    controller.paintNow();
    let paints = -1;
    watchEffect(
      () => {
        controller.tabs.resolve();
        paints += 1;
      },
      { flush: "sync" },
    );

    await controller.refresh({ background: true });

    expect(paints).toBe(0);
  });

  it("draws once, and only the overlay that changed", async () => {
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("status", page.doc.status));
        page.fields.hide("rate");
      },
    });
    const { controller, doc } = await loadedPage();
    controller.paintNow();
    const paints = countPaints(controller);

    doc.value = { status: "Won" };
    await controller.refresh({ background: true });

    expect(paints).toEqual({ actions: 1, fields: 0 });
    expect(drawn(controller)).toEqual(["Won"]);
  });
});
