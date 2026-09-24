// The first paint's time limit: a late source is left out, named, and lands when it finishes.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

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
import {
  createRecordPage,
  FIRST_PAINT_LIMIT_MS,
  type RecordPageHost,
} from "../createRecordPage";
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
  it("paints the finished sources, names the late one, and draws it when it finishes", async () => {
    let finish!: () => void;
    const late = new Promise<void>((resolve) => (finish = resolve));
    await register("early", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        page.fields.hide("f1");
      },
    });
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        page.quickActions.add(action("two"));
        page.fields.hide("f2");
        page.form.tabs.hide("t2");
        await late;
        page.quickActions.add(action("three"));
      },
    });
    const controller = makePage();

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["one"]);
    expect(Object.keys(controller.fields.resolve())).toEqual(["f1"]);
    expect(controller.form.tabs.resolve()).toEqual({});
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain("without waiting for slow");

    finish();
    await refreshing;

    expect(drawn(controller)).toEqual(["one", "two", "three"]);
    expect(Object.keys(controller.fields.resolve())).toEqual(["f1", "f2"]);
    expect(Object.keys(controller.form.tabs.resolve())).toEqual(["t2"]);
    expect(warnings).toHaveLength(1);
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
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        page.quickActions.add(action("one"));
        await new Promise<void>(() => {});
      },
    });
    const controller = makePage();

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
    await register("slow", {
      onRefresh: async (page: RecordPageApi) => {
        page.quickActions.add(action(`run-${++replays}`));
        if (replays > 1) await new Promise<void>((resolve) => (finish = resolve));
      },
    });
    const controller = makePage();
    await controller.refresh();

    const refreshing = controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS * 2);

    expect(drawn(controller)).toEqual(["run-1"]);
    expect(warnings).toEqual([]);
    finish();
    await refreshing;
    expect(drawn(controller)).toEqual(["run-2"]);
  });
});
