// `page.cached`: a kept value paints at once on a return visit, and a cold load's first paint waits for it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref, watch, watchEffect } from "vue";

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
      method === GET_CLIENT_SCRIPTS ? { data: { scripts: [], can_write: false } } : { data: null },
    ),
    getMeta: vi.fn(async () => ({ data: null })),
  };
});

import {
  clearDataCache,
  feedDelete,
  feedRecordRead,
  RECORD_PARTS,
  takeTicket,
} from "@framework/ui/cache";
import { loadClientScripts, resetClientScripts } from "../clientScripts";
import { createRecordPage } from "../createRecordPage";
import { withRegisteringSource } from "../context";
import { resetKeptValues } from "../keptValues";
import { FIRST_PAINT_LIMIT_MS, LATE_LIMIT_MS } from "../paintGate";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, RecordPageApi } from "../types";

const DOCTYPE = "CRM Deal";
const DOCNAME = "CRM-DEAL-1";

type Controller = ReturnType<typeof createRecordPage>;

async function visit() {
  await loadClientScripts(DOCTYPE);
  const moved: string[] = [];
  const controller = createRecordPage({
    doctype: DOCTYPE,
    docname: DOCNAME,
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
    sourcesReady: () => loadClientScripts(DOCTYPE),
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
  });
  controller.tabs.provideBuiltins(() => [
    { name: "details", label: "Details" },
    { name: "notes", label: "Notes" },
  ] as any[]);
  await vi.advanceTimersByTimeAsync(0);
  return { controller, moved };
}

/** A cold load: the first replay, and every fetch it waits for. */
async function coldVisit() {
  const made = await visit();
  await made.controller.refresh();
  await vi.advanceTimersByTimeAsync(0);
  made.controller.leave();
  return made;
}

/** The host's steps after a return visit's paint: the background reads, then one replay. */
async function backgroundReads(controller: Controller) {
  await controller.fetchCached();
  await controller.refresh({ background: true });
}

function register(source: string, handlers: AuthoredHandlers) {
  return withRegisteringSource(source, async () => registerRecordPage(DOCTYPE, handlers));
}

/** A script that draws a credit limit from the server as a quick action. */
function creditLimitScript(fetchLimit: () => Promise<unknown>, source = "credit") {
  return register(source, {
    onRefresh: (page: RecordPageApi) => {
      const limit = page.cached("credit-limit", fetchLimit);
      page.quickActions.add({ name: source, label: `${source} ${limit ?? "-"}`, run });
    },
  });
}

const run = () => {};

function cacheRecord() {
  const parts = Object.fromEntries(RECORD_PARTS.map((part) => [part, []]));
  const envelope = { data: { name: DOCNAME, modified: "2026-09-30 10:00:00" }, ...parts };
  feedRecordRead(takeTicket(), DOCTYPE, envelope as any, RECORD_PARTS, 1000);
}

const drawn = (controller: Controller) =>
  controller.quickActions.visible().map((one) => one.label);

function countPaints(controller: Controller) {
  const paints = { count: -1 };
  watchEffect(
    () => {
      controller.quickActions.resolve();
      paints.count += 1;
    },
    { flush: "sync" },
  );
  return paints;
}

function deferred<T>() {
  let settle!: (value: T) => void;
  let fail!: (error: unknown) => void;
  const promise = new Promise<T>((resolve, reject) => {
    settle = resolve;
    fail = reject;
  });
  return { promise, settle, fail };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetClientScripts();
  clearDataCache();
  resetKeptValues();
  cacheRecord();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => void warnings.push(message));
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("page.cached on a return visit", () => {
  it("paints the kept value at once, and draws nothing when the background reads bring the same value", async () => {
    const fetchLimit = vi.fn(async () => 5000);
    await creditLimitScript(fetchLimit);
    await coldVisit();
    const { controller } = await visit();

    controller.paintNow();

    expect(drawn(controller)).toEqual(["credit 5000"]);
    const paints = countPaints(controller);
    await backgroundReads(controller);
    expect(paints.count).toBe(0);
    expect(fetchLimit).toHaveBeenCalledTimes(2);
  });

  it("draws a value that changed after the background reads in one paint", async () => {
    const limits = [5000, 7500];
    await creditLimitScript(async () => limits.shift());
    await coldVisit();
    const { controller } = await visit();
    controller.paintNow();
    const paints = countPaints(controller);

    await backgroundReads(controller);

    expect(drawn(controller)).toEqual(["credit 7500"]);
    expect(paints.count).toBe(1);
  });

  it("stops waiting for a fetch at the late limit, so the other background reads still apply", async () => {
    const fetches = [async () => 5000, () => new Promise<number>(() => {})];
    await creditLimitScript(() => fetches.shift()!());
    await coldVisit();
    const { controller } = await visit();
    controller.paintNow();
    let replayed = false;

    void backgroundReads(controller).then(() => (replayed = true));
    await vi.advanceTimersByTimeAsync(LATE_LIMIT_MS);

    expect(replayed).toBe(true);
    expect(drawn(controller)).toEqual(["credit 5000"]);
    expect(warnings.at(-1)).toContain("credit page.cached on CRM Deal did not settle within 5 s");
  });

  it("drops an act made in the replay that draws the fetched value", async () => {
    await register("credit", {
      onRefresh: (page: RecordPageApi) => {
        page.cached("credit-limit", async () => 5000);
        page.tabs.activate("notes");
      },
    });
    await coldVisit();
    const { controller, moved } = await visit();
    controller.paintNow();

    await backgroundReads(controller);

    expect(moved).toEqual(["notes"]);
  });
});

describe("page.cached on a cold load", () => {
  it("holds the first paint until the fetch lands, then paints its value once", async () => {
    const limit = deferred<number>();
    await creditLimitScript(() => limit.promise);
    const { controller } = await visit();
    const atReady: string[][] = [];
    watch(controller.ready, () => atReady.push(drawn(controller)), { flush: "sync" });

    await controller.refresh();
    expect(controller.ready.value).toBe(false);
    limit.settle(5000);
    await vi.advanceTimersByTimeAsync(0);

    expect(atReady).toEqual([["credit 5000"]]);
  });

  it("paints without the script after 500 ms, then draws its value when the fetch lands", async () => {
    const limit = deferred<number>();
    await creditLimitScript(() => limit.promise);
    await register("other", {
      onRefresh: (page: RecordPageApi) => page.quickActions.add({ name: "other", label: "other", run }),
    });
    const { controller } = await visit();

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(FIRST_PAINT_LIMIT_MS);

    expect(controller.ready.value).toBe(true);
    expect(drawn(controller)).toEqual(["other"]);
    expect(warnings.at(-1)).toContain("without waiting for credit");
    limit.settle(5000);
    await vi.advanceTimersByTimeAsync(0);
    expect(drawn(controller)).toEqual(["credit 5000", "other"]);
  });

  it("paints the kept value and replaces it with the fetched one before the first paint", async () => {
    const limits = [5000, 7500];
    await creditLimitScript(async () => limits.shift());
    await coldVisit();
    const { controller } = await visit();
    const atReady: string[][] = [];
    watch(controller.ready, () => atReady.push(drawn(controller)), { flush: "sync" });

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(0);

    expect(atReady).toEqual([["credit 7500"]]);
  });

  it("lands an onRefresh act once, though the replay runs again for the fetch", async () => {
    await register("credit", {
      onRefresh: (page: RecordPageApi) => {
        page.cached("credit-limit", async () => 5000);
        page.tabs.activate("notes");
      },
    });
    const { controller, moved } = await visit();

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(0);

    expect(moved).toEqual(["notes"]);
  });
});

describe("page.cached", () => {
  it("fetches a key once per visit, however many replays read it", async () => {
    const fetchLimit = vi.fn(async () => 5000);
    await creditLimitScript(fetchLimit);
    const { controller } = await visit();

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(0);
    await controller.page.refresh();
    await controller.refresh({ background: true });

    expect(fetchLimit).toHaveBeenCalledTimes(1);
  });

  it("fetches once per replay a key that changes on every replay", async () => {
    let replays = 0;
    const fetchLimit = vi.fn(async () => 5000);
    await register("credit", {
      onRefresh: (page: RecordPageApi) => void page.cached(`limit:${(replays += 1)}`, fetchLimit),
    });
    const { controller } = await visit();

    await controller.refresh();
    await vi.advanceTimersByTimeAsync(LATE_LIMIT_MS);

    expect(fetchLimit).toHaveBeenCalledTimes(1);
    expect(controller.ready.value).toBe(true);
  });

  it("keeps the last value and names the script when a fetch fails", async () => {
    const [kept, failing] = [deferred<number>(), deferred<number>()];
    const fetches = [kept, failing];
    await creditLimitScript(() => fetches.shift()!.promise);
    const first = await visit();
    await first.controller.refresh();
    kept.settle(5000);
    await vi.advanceTimersByTimeAsync(0);
    first.controller.leave();
    const { controller } = await visit();
    controller.paintNow();

    failing.fail(new Error("timed out"));
    await backgroundReads(controller);

    expect(drawn(controller)).toEqual(["credit 5000"]);
    expect(warnings.at(-1)).toBe(
      '[record-page] credit page.cached("credit-limit") on CRM Deal failed; the page keeps its last value.',
    );
  });

  it("keeps each script's values apart, so two scripts may use one key", async () => {
    await creditLimitScript(async () => 5000, "credit");
    await creditLimitScript(async () => 900, "overdue");
    await coldVisit();
    const { controller } = await visit();

    controller.paintNow();

    expect(drawn(controller)).toEqual(["credit 5000", "overdue 900"]);
  });

  it("drops the kept value with the record's cache entry", async () => {
    await creditLimitScript(async () => 5000);
    await coldVisit();
    feedDelete(takeTicket(), DOCTYPE, DOCNAME);
    cacheRecord();
    const { controller } = await visit();

    controller.paintNow();

    expect(drawn(controller)).toEqual(["credit -"]);
  });

  it("keeps nothing a fetch brings after the record's entry left and came back", async () => {
    const limit = deferred<number>();
    await creditLimitScript(() => limit.promise);
    const first = await visit();
    await first.controller.refresh();
    feedDelete(takeTicket(), DOCTYPE, DOCNAME);
    cacheRecord();

    limit.settle(5000);
    await vi.advanceTimersByTimeAsync(0);
    first.controller.leave();
    const { controller } = await visit();
    controller.paintNow();

    expect(drawn(controller)).toEqual(["credit -"]);
  });

  it("keeps nothing for a record the shared cache holds no complete entry of", async () => {
    clearDataCache();
    await creditLimitScript(async () => 5000);
    await coldVisit();
    cacheRecord();
    const { controller } = await visit();

    controller.paintNow();

    expect(drawn(controller)).toEqual(["credit -"]);
  });
});
