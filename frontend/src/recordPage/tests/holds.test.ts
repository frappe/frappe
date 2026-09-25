// A handler's ops paint once, when it finishes, and its acts land after that paint.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watchEffect } from "vue";

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
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { HOST_SOURCE, runningSource, withRegisteringSource } from "../context";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

const RECORD_TABS = [
  { name: "details", label: "Details" },
  { name: "activity", label: "Activity" },
];

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const moved: { tab: string; drawn: string[] }[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => true,
    activeTab: () => "details",
    activateTab: (tab) =>
      void moved.push({ tab, drawn: controller.tabs.visible().map((one) => one.name) }),
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
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
  return { controller, page: controller.page, moved };
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage("CRM Deal", handlers));
}

function gate() {
  let open!: () => void;
  const opened = new Promise<void>((resolve) => (open = resolve));
  return { opened, open };
}

function action(name: string) {
  return { name, label: name, run: () => {} };
}

/** How many times each drawn overlay changed, counted by a sync effect over its `resolve()`. */
function countPaints(controller: ReturnType<typeof makePage>["controller"]) {
  const paints = { count: -1, fields: -1, formTabs: -1 };
  const count = (key: keyof typeof paints, read: () => unknown) =>
    watchEffect(
      () => {
        read();
        paints[key] += 1;
      },
      { flush: "sync" },
    );
  count("count", () => controller.quickActions.resolve());
  count("fields", () => controller.fields.resolve());
  count("formTabs", () => controller.form.tabs.resolve());
  return paints;
}

const drawn = (controller: ReturnType<typeof makePage>["controller"]) =>
  controller.quickActions.visible().map((one) => one.name);

beforeEach(() => {
  resetRegistry();
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("one paint per handler", () => {
  it("draws a handler's verbs in one write, and `has` sees its first verb before the await", async () => {
    const pause = gate();
    let seen: boolean | undefined;
    await register("deal", {
      qty: async (page: RecordPageApi) => {
        page.quickActions.add(action("first"));
        seen = page.quickActions.has("first");
        await pause.opened;
        page.quickActions.add(action("second"));
      },
    });
    const { controller } = makePage();
    await controller.refresh();
    const paints = countPaints(controller);

    const firing = controller.fireEvent("qty");
    await Promise.resolve();
    expect(seen).toBe(true);
    expect(drawn(controller)).toEqual([]);
    pause.open();
    await firing;

    expect(drawn(controller)).toEqual(["first", "second"]);
    expect(paints.count).toBe(1);
  });

  it("holds every source's handler for one event under one paint", async () => {
    await register("one", { qty: (page: RecordPageApi) => page.quickActions.add(action("a")) });
    await register("two", {
      qty: (page: RecordPageApi) => {
        page.quickActions.add(action("b"));
        page.fields.hide("rate");
      },
    });
    const { controller } = makePage();
    await controller.refresh();
    const paints = countPaints(controller);

    await controller.fireEvent("qty");

    expect(paints.count).toBe(1);
    expect(drawn(controller)).toEqual(["a", "b"]);
    expect(controller.fields.resolve().rate?.override?.hidden).toBe(true);
  });

  it("draws nothing again for a handler that recorded nothing", async () => {
    await register("deal", { qty: () => {} });
    const { controller } = makePage();
    await controller.refresh();
    const paints = countPaints(controller);

    await controller.fireEvent("qty");

    expect(paints.count).toBe(0);
  });

  it("publishes a throwing handler's ops", async () => {
    await register("deal", {
      qty: (page: RecordPageApi) => {
        page.quickActions.add(action("kept"));
        throw new Error("boom");
      },
    });
    const { controller } = makePage();
    await controller.refresh();

    await controller.fireEvent("qty");

    expect(drawn(controller)).toEqual(["kept"]);
  });

  it("publishes a vetoing `beforeSave`'s ops", async () => {
    await register("deal", {
      beforeSave: (page: RecordPageApi) => {
        page.quickActions.add(action("kept"));
        throw new Error("not yet");
      },
    });
    const { controller, page } = makePage();
    await controller.refresh();

    await expect(page.save()).rejects.toMatchObject({ name: SAVE_VETO });

    expect(drawn(controller)).toEqual(["kept"]);
  });

  it("holds the host's own call into script code", async () => {
    const { controller, page } = makePage();
    await controller.refresh();
    const paints = countPaints(controller);
    const pause = gate();

    const running = controller.hold(async () => {
      page.quickActions.add(action("a"));
      await pause.opened;
      page.quickActions.add(action("b"));
      return "done";
    });
    await Promise.resolve();
    expect(drawn(controller)).toEqual([]);
    pause.open();

    await expect(running).resolves.toBe("done");
    expect(drawn(controller)).toEqual(["a", "b"]);
    expect(paints.count).toBe(1);
  });
});

describe("a hold and a replay that overlap", () => {
  it("publish once, when the hold that outlives the replay ends", async () => {
    const pause = gate();
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("replayed"));
        page.fields.hide("rate");
      },
      qty: async (page: RecordPageApi) => {
        await pause.opened;
        page.quickActions.add(action("held"));
        page.form.tabs.hide("notes");
      },
    });
    const { controller } = makePage();
    await controller.refresh();
    const paints = countPaints(controller);

    const firing = controller.fireEvent("qty");
    await controller.refresh();
    expect(paints).toEqual({ count: 0, fields: 0, formTabs: 0 });
    pause.open();
    await firing;

    expect(paints).toEqual({ count: 1, fields: 0, formTabs: 1 });
    expect(drawn(controller)).toEqual(["replayed", "held"]);
  });

  it("publish once, when the replay that outlives the hold ends", async () => {
    const pause = gate();
    let replays = 0;
    await register("deal", {
      onRefresh: (page: RecordPageApi) => {
        page.quickActions.add(action("replayed"));
        if (++replays > 1) page.fields.hide("rate");
      },
      qty: (page: RecordPageApi) => {
        page.quickActions.add(action("held"));
        page.form.tabs.hide("notes");
      },
    });
    const { controller } = makePage({
      sourcesReady: () => (replays ? pause.opened : Promise.resolve()),
    });
    await controller.refresh();
    const paints = countPaints(controller);

    const replaying = controller.refresh();
    await vi.waitFor(() => expect(replays).toBe(2));
    await controller.fireEvent("qty");
    expect(paints).toEqual({ count: 0, fields: 0, formTabs: 0 });
    pause.open();
    await replaying;

    expect(paints).toEqual({ count: 1, fields: 1, formTabs: 1 });
    expect(drawn(controller)).toEqual(["replayed", "held"]);
  });
});

describe("acts inside a handler", () => {
  it("move the reader only once the hold has drawn the tab", async () => {
    await register("deal", {
      qty: async (page: RecordPageApi) => {
        page.tabs.add({ name: "custom", label: "Custom", component: {} } as any);
        page.tabs.activate("custom");
        await Promise.resolve();
      },
    });
    const { controller, moved } = makePage();
    await controller.refresh();

    const firing = controller.fireEvent("qty");
    await Promise.resolve();
    expect(moved).toEqual([]);
    await firing;

    expect(moved).toEqual([{ tab: "custom", drawn: ["details", "activity", "custom"] }]);
  });
});

describe("the running source", () => {
  it("names each of two overlapping handlers until it settles, then the host", async () => {
    const first = gate();
    const second = gate();
    const seen: string[] = [];
    await register("A", { qty: () => first.opened });
    await register("B", {
      rate: async () => {
        await second.opened;
        seen.push(runningSource());
      },
    });
    const { controller } = makePage();
    await controller.refresh();

    const a = controller.fireEvent("qty");
    const b = controller.fireEvent("rate");
    first.open();
    await a;
    second.open();
    await b;

    expect(seen).toEqual(["B"]);
    expect(runningSource()).toBe(HOST_SOURCE);
  });
});
