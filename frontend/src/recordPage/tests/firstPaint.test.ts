// The first paint's time limit: what a replay waits for is named, and lands when it arrives.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watchEffect } from "vue";

const scripts = vi.hoisted(() => ({ list: new Promise<never>(() => {}) }));

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

import { clientScriptWait, loadClientScripts, resetClientScripts } from "../clientScripts";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { FIRST_PAINT_LIMIT_MS } from "../paintGate";
import { withRegisteringSource } from "../context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
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
    ...overrides,
  };
  return createRecordPage(host);
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage("CRM Deal", handlers));
}

function action(name: string) {
  return { name, label: name, run: () => {} };
}

const drawn = (controller: ReturnType<typeof makePage>) =>
  controller.quickActions.visible().map((one) => one.name);

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

const never = () => new Promise<void>(() => {});

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetClientScripts();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("the first paint's time limit", () => {
  it("paints the file scripts, names the scripts it waits for, and draws the late ones when they arrive", async () => {
    const list = gate();
    await register("early", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        page.fields.hide("f1");
      },
    });
    const controller = makePage({ sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one"]);
    expect(Object.keys(controller.fields.resolve())).toEqual(["f1"]);
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain("without waiting for the page's scripts");

    await register("client-script:late", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("two"));
        page.fields.hide("f2");
        page.form.tabs.hide("t2");
      },
    });
    list.open();
    await refreshing;

    expect(drawn(controller)).toEqual(["one", "two"]);
    expect(Object.keys(controller.fields.resolve())).toEqual(["f1", "f2"]);
    expect(Object.keys(controller.form.tabs.resolve())).toEqual(["t2"]);
    expect(warnings).toHaveLength(1);
  });

  it("names the scripts it waits for, not a hold running beside them", async () => {
    await register("G", { onTabChange: never });
    const controller = makePage({ sourcesReady: never });

    void controller.fireEvent("onTabChange");
    void controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(warnings[0]).toContain("without waiting for the page's scripts");
  });

  it("warns nothing when the first refresh finishes inside the limit", async () => {
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
    });
    const controller = makePage();

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS * 2);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one"]);
    expect(warnings).toEqual([]);
  });

  it("paints the file scripts while the Client Script list is still being fetched", async () => {
    await register("file", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
    });
    const controller = makePage({ sourcesReady: () => loadClientScripts("CRM Deal") });

    void controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(clientScriptWait("CRM Deal")).toBe("the Client Script list for CRM Deal");
    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one"]);
    expect(warnings[0]).toContain("without waiting for the Client Script list for CRM Deal");
  });

  it("stays quiet when the reader leaves before the limit", async () => {
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("one")),
    });
    const controller = makePage({ sourcesReady: never });

    void controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS / 2);
    controller.leave();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS * 2);

    expect(controller.ready.value).toBe(false);
    expect(drawn(controller)).toEqual([]);
    expect(warnings).toEqual([]);
  });

  it("keeps a later refresh waiting for its scripts, as before", async () => {
    let finish!: () => void;
    let replays = 0;
    let lists = 0;
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action(`run-${++replays}`)),
    });
    const controller = makePage({
      sourcesReady: () =>
        ++lists > 1 ? new Promise<void>((resolve) => (finish = resolve)) : Promise.resolve(),
    });
    await controller.refresh();

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS * 2);

    expect(drawn(controller)).toEqual(["run-1"]);
    expect(warnings).toEqual([]);
    finish();
    await refreshing;
    expect(drawn(controller)).toEqual(["run-2"]);
  });

  it("leaves a running `beforeSave` out of the early paint and draws it once, when it ends", async () => {
    const guard = gate();
    await register("A", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("a-op"));
        void page.save();
      },
    });
    await register("G", {
      beforeSave: async (page: RecordPageApi) => {
        page.quickActions.add(action("g-partial"));
        await guard.opened;
        page.quickActions.add(action("g-late"));
      },
    });
    await register("B", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add(action("b-op")),
    });
    const controller = makePage({ isDirty: () => true });
    let writes = -1;
    watchEffect(
      () => {
        controller.quickActions.resolve();
        writes += 1;
      },
      { flush: "sync" },
    );

    void controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["a-op", "b-op"]);
    expect(warnings[0]).toContain("without waiting for G;");
    expect(writes).toBe(1);

    guard.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(drawn(controller)).toEqual(["a-op", "b-op", "g-partial", "g-late"]);
    expect(writes).toBe(2);
  });

  it("shows the file scripts' feed types in the early paint, and a late script's after", async () => {
    const list = gate();
    await register("early", {
      onRefresh: (page: RecordPageApi) => page.activity.types(["comment"]),
    });
    const controller = makePage({ sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);
    expect(controller.activity.shownTypes()).toEqual(["comment"]);

    await register("client-script:late", {
      onRefresh: (page: RecordPageApi) => page.activity.types(["email"]),
    });
    list.open();
    await refreshing;
    expect(controller.activity.shownTypes()).toEqual(["email"]);
  });

  it("arms no clock and runs nothing when the page was already left", async () => {
    const onRefresh = vi.fn();
    await register("early", { onRefresh });
    const controller = makePage();
    controller.leave();

    await controller.refresh();

    expect(vi.getTimerCount()).toBe(0);
    expect(onRefresh).not.toHaveBeenCalled();
  });

  it("lifts the skeletons at once when the scripts fail to load, and warns nothing", async () => {
    const controller = makePage({ sourcesReady: () => Promise.reject(new Error("offline")) });

    await expect(controller.refresh()).rejects.toThrow("offline");

    expect(controller.ready.value).toBe(true);
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS * 2);
    expect(warnings).toEqual([]);
  });
});

describe("ready", () => {
  it("waits for a save a replay handler started, when its hold closes last", async () => {
    const list = gate();
    const started = gate();
    const guard = gate();
    await register("saver", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("replayed"));
        void page.save();
      },
    });
    await register("guard", {
      beforeSave: async () => {
        started.open();
        await guard.opened;
      },
    });
    const controller = makePage({ isDirty: () => true, sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    await started.opened;
    list.open();
    await refreshing;
    expect(controller.ready.value).toBe(false);
    expect(drawn(controller)).toEqual([]);

    guard.open();
    await vi.advanceTimersByTimeAsync(0);
    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["replayed"]);
  });

  it("does not wait for an onRefresh that returns a promise, and warns about it", async () => {
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        await never();
      },
    });
    const controller = makePage();

    await controller.refresh();

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one"]);
    expect(warnings).toEqual([
      "[record-page] slow.onRefresh on CRM Deal returned a promise, which is not awaited; onRefresh is synchronous.",
    ]);
  });

  it("stays false through a nested `page.refresh()` until the outer replay ends", async () => {
    const outer = gate();
    let lists = 0;
    let inner: Promise<void> | undefined;
    const controller = makePage({
      sourcesReady: () => (++lists === 1 ? outer.opened : Promise.resolve()),
    });
    await register("nested", {
      onRefresh: (page: RecordPageApi) => void (inner ??= page.refresh()),
    });

    const refreshing = controller.refresh();
    await vi.waitFor(() => expect(inner).toBeDefined());
    await inner;
    expect(controller.ready.value).toBe(false);

    outer.open();
    await refreshing;
    expect(controller.ready.value).toBe(true);
  });

  it("runs a source that registers between the two passes once, in order", async () => {
    const order: string[] = [];
    let answerList!: () => void;
    const list = new Promise<void>((resolve) => (answerList = resolve));
    await register("file", { onRefresh: () => void order.push("file") });
    const controller = makePage({ sourcesReady: () => list });

    const refreshing = controller.refresh();
    await vi.waitFor(() => expect(order).toEqual(["file"]));
    await register("client-script:late", { onRefresh: () => void order.push("client") });
    answerList();
    await refreshing;

    expect(order).toEqual(["file", "client"]);
  });
});

describe("acts held at the early paint", () => {
  const RECORD_TABS = [
    { name: "details", label: "Details" },
    { name: "activity", label: "Activity" },
  ];

  function makeActingPage(overrides: Partial<RecordPageHost> = {}) {
    const moved: { tab: string; drawn: string[] }[] = [];
    const focused: string[] = [];
    const scrolled: string[] = [];
    const opened: string[] = [];
    const controller = makePage({
      meta: ref({ fields: [{ fieldname: "qty", fieldtype: "Int" }] }),
      activateTab: (tab) =>
        void moved.push({ tab, drawn: controller.tabs.visible().map((one) => one.name) }),
      focusField: (fieldname) => void focused.push(fieldname),
      scrollToActivity: async (key) => Boolean(scrolled.push(key)),
      openWriter: (name) => void opened.push(name),
      ...overrides,
    });
    controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
    return { controller, moved, focused, scrolled, opened };
  }

  const tab = (name: string) => ({ name, label: name, component: {} }) as any;

  it("delivers a finished source's tab move and focus, and drops an open of a section not drawn", async () => {
    const list = gate();
    await register("early", {
      onRefresh: (page: RecordPageApi) => {
        page.tabs.add(tab("custom"));
        page.tabs.activate("custom");
        page.fields.focus("qty");
        void page.save();
      },
    });
    await register("guard", {
      beforeSave: async (page: RecordPageApi) => {
        page.panelSections.add({ name: "late", label: "Late" } as any);
        page.panelSections.open("late");
        await never();
      },
    });
    const { controller, moved, focused } = makeActingPage({
      isDirty: () => true,
      sourcesReady: () => list.opened,
    });

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(moved).toEqual([{ tab: "custom", drawn: ["details", "activity", "custom"] }]);
    expect(focused).toEqual(["qty"]);
    expect(warnings.some((one) => one.includes('open("late")') && one.includes("first paint"))).toBe(
      true,
    );

    list.open();
    await refreshing;
    expect(moved).toHaveLength(1);
    expect(focused).toEqual(["qty"]);
  });

  it("delivers a finished source's feed scroll and composer open", async () => {
    await register("early", {
      onRefresh: (page: RecordPageApi) => {
        page.activity.add({ name: "mine", timestamp: "2026-09-24 10:00:00", component: {} } as any);
        page.activity.scrollTo("mine");
        page.composer.add({ name: "call", label: "Log a call", component: {} } as any);
        page.composer.open("call");
      },
    });
    const { controller, moved, scrolled, opened } = makeActingPage({ sourcesReady: never });

    void controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(scrolled).toEqual(["mine"]);
    expect(opened).toEqual(["call"]);
    expect(moved.map((one) => one.tab)).toEqual(["activity"]);
  });

  it("keeps a move asked for after the early paint until the final commit", async () => {
    const list = gate();
    const { controller, moved } = makeActingPage({ sourcesReady: () => list.opened });

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);
    expect(moved).toEqual([]);

    await register("client-script:late", {
      onRefresh: (page: RecordPageApi) => {
        page.tabs.add(tab("later"));
        page.tabs.activate("later");
      },
    });
    list.open();
    await refreshing;
    expect(moved).toEqual([{ tab: "later", drawn: ["details", "activity", "later"] }]);
  });
});
