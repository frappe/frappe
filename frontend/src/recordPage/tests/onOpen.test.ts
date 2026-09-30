// `onOpen`: once per page, after the first replay has committed, never on a replay.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watch } from "vue";

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

import { loadClientScripts, resetClientScripts } from "../clientScripts";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { FIRST_PAINT_LIMIT_MS } from "../paintGate";
import { withRegisteringSource } from "../context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

const RECORD_TABS = [
  { name: "details", label: "Details" },
  { name: "files", label: "Files" },
];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const moved: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
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
  return { controller, moved };
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

function action(name: string) {
  return { name, label: name, run: () => {} };
}

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

/** Counts each handler's calls, and what `onOpen` saw drawn when it ran. */
function counting() {
  const calls = { onRefresh: 0, onOpen: 0 };
  const seen: boolean[] = [];
  const handlers = {
    onRefresh: (page: RecordPageApi) => {
      calls.onRefresh += 1;
      page.quickActions.add(action("mine"));
    },
    onOpen: (page: RecordPageApi) => {
      calls.onOpen += 1;
      seen.push(page.quickActions.has("mine"));
      page.tabs.activate("files");
    },
  };
  return { calls, seen, handlers };
}

beforeEach(() => {
  resetRegistry();
  resetClientScripts();
  scripts.list = Promise.resolve({ data: { scripts: [], can_write: false } });
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("onOpen on a return visit", () => {
  it("runs once, after the paint from memory, and never on a replay", async () => {
    const { calls, seen, handlers } = counting();
    await register("deal", handlers);
    const { controller, moved } = await loadedPage();

    controller.paintNow();

    expect(calls).toEqual({ onRefresh: 1, onOpen: 1 });
    expect(seen).toEqual([true]);
    expect(moved).toEqual(["files"]);

    await controller.refresh({ background: true });
    await controller.refresh();
    await controller.page.refresh();

    expect(calls).toEqual({ onRefresh: 4, onOpen: 1 });
    expect(moved).toEqual(["files"]);
  });

  it("runs again on the next visit, which builds a new page", async () => {
    const { calls, handlers } = counting();
    await register("deal", handlers);

    const first = await loadedPage();
    first.controller.paintNow();
    first.controller.leave();
    const second = await loadedPage();
    second.controller.paintNow();

    expect(calls.onOpen).toBe(2);
    expect(second.moved).toEqual(["files"]);
  });

  it("waits for an onRefresh's part after its await, and then sees what it drew", async () => {
    const pause = gate();
    const seen: boolean[] = [];
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        const { quickActions } = page;
        await pause.opened;
        quickActions.add(action("late"));
      },
      onOpen: (page: RecordPageApi) => void seen.push(page.quickActions.has("late")),
    });
    const { controller } = await loadedPage();

    controller.paintNow();
    await vi.advanceTimersByTimeAsync(0);
    expect(seen).toEqual([]);

    pause.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(seen).toEqual([true]);
  });
});

describe("onOpen on a first visit", () => {
  it("lands its acts before the skeletons lift, so the first tab shown is the one it chose", async () => {
    const { calls, handlers } = counting();
    await register("deal", handlers);
    const { controller, moved } = makePage();
    const movedAtReady: string[][] = [];
    watch(controller.ready, () => void movedAtReady.push([...moved]), { flush: "sync" });

    await controller.refresh();

    expect(calls).toEqual({ onRefresh: 1, onOpen: 1 });
    expect(movedAtReady).toEqual([["files"]]);

    await controller.refresh();
    expect(calls).toEqual({ onRefresh: 2, onOpen: 1 });
  });

  it("runs a late script's onOpen after that script's ops land, not at the early paint", async () => {
    const list = gate();
    const seen: string[] = [];
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
      onOpen: () => void seen.push("early"),
    });
    const { controller } = makePage({ sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);
    expect(controller.ready.value).toBe(true);
    expect(seen).toEqual([]);

    await register("client-script:late", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("two")),
      onOpen: (page: RecordPageApi) => void seen.push(`late sees two: ${page.quickActions.has("two")}`),
    });
    list.open();
    await refreshing;

    expect(seen).toEqual(["early", "late sees two: true"]);
  });

  it("runs nothing when the reader left before the first replay ended", async () => {
    const list = gate();
    const { calls, handlers } = counting();
    await register("deal", handlers);
    const { controller } = makePage({ sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    controller.leave();
    list.open();
    await refreshing;

    expect(calls.onOpen).toBe(0);
  });
});

describe("onOpen's errors and awaits", () => {
  it("reports a throw, and the next source's onOpen still runs", async () => {
    const seen: string[] = [];
    await register("broken", {
      onOpen: () => {
        throw new Error("boom");
      },
    });
    await register("fine", { onOpen: () => void seen.push("fine") });
    const { controller } = await loadedPage();

    controller.paintNow();

    expect(seen).toEqual(["fine"]);
    expect(console.error).toHaveBeenCalledWith(
      "[record-page] broken.onOpen on CRM Deal threw",
      expect.any(Error),
    );
  });

  it("lands an act made after an await at once, and nothing once the reader has left", async () => {
    const pause = gate();
    await register("deal", {
      onOpen: async (page: RecordPageApi) => {
        await pause.opened;
        page.tabs.activate("files");
      },
    });
    const first = await loadedPage();
    first.controller.paintNow();

    pause.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(first.moved).toEqual(["files"]);

    const later = gate();
    resetRegistry();
    await register("deal", {
      onOpen: async (page: RecordPageApi) => {
        await later.opened;
        page.tabs.activate("files");
      },
    });
    const second = await loadedPage();
    second.controller.paintNow();
    second.controller.leave();
    later.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(second.moved).toEqual([]);
  });
});
