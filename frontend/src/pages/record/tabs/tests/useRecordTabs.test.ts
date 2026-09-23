// The page's strip wiring, run as the page runs it: which tab paints, and when each tab event fires.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, reactive, ref, shallowRef, type EffectScope } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { createRecordPage, type RecordPageController } from "@/recordPage/createRecordPage";
import { registerRecordPage, resetRegistry } from "@/recordPage/registry";
import { recordTabBuiltins } from "../recordTabs";
import { useRecordTabs } from "../useRecordTabs";

let warnings: string[];
let scope: EffectScope;

beforeEach(() => {
  resetRegistry();
  warnings = [];
  scope = effectScope();
  vi.spyOn(console, "warn").mockImplementation((message: string) => warnings.push(message));
});

afterEach(() => scope.stop());

/** One record page wired as the generated page wires it, with a router that settles a tick later. */
function makePage(query: Record<string, string> = {}) {
  const route = reactive({ query: { ...query } as Record<string, any>, hash: "" });
  const router = {
    replace: vi.fn(async (to: { query: Record<string, any> }) => {
      await Promise.resolve();
      route.query = to.query;
    }),
  } as any;
  const controller = shallowRef<RecordPageController | null>(null);
  const formTab = ref("");
  const tabs = scope.run(() =>
    useRecordTabs({ route: route as any, router, controller: () => controller.value, formTab: () => formTab.value }),
  )!;
  const open = () => {
    controller.value = createRecordPage({
      doctype: "CRM Deal",
      docname: "CRM-DEAL-1",
      doc: ref({}),
      saved: ref({}),
      meta: ref(null),
      perms: () => ({}),
      isDirty: () => false,
      ...tabs.pageHost,
      save: async () => {},
      reload: async () => {},
      router,
      activityRows: () => [],
      scrollToActivity: async () => false,
      reloadActivity: async () => {},
      fileRows: () => [],
      reloadFiles: async () => {},
    });
    controller.value.tabs.provideBuiltins(recordTabBuiltins);
    return controller.value.refresh().then(settle);
  };
  return { controller, formTab, route, tabs, open };
}

async function settle() {
  for (let turn = 0; turn < 3; turn++) await nextTick();
}

describe("the painted tab", () => {
  it("is nothing until the first replay commits", async () => {
    let seen = "unset";
    registerRecordPage("CRM Deal", {
      onRefresh: () => void (seen = page.tabs.shown.value),
    });
    const page = makePage();

    await page.open();

    expect(seen).toBe("");
    expect(page.tabs.shown.value).toBe("activity");
  });

  it("follows a hide after a click made while a replay was in flight", async () => {
    let release = () => {};
    let hold = false;
    registerRecordPage("CRM Deal", {
      onRefresh: () => (hold ? new Promise<void>((resolve) => (release = resolve)) : undefined),
    });
    const page = makePage();
    await page.open();

    hold = true;
    const replay = page.controller.value!.refresh();
    await settle();
    expect(page.controller.value!.isReplaying.value).toBe(true);
    await page.tabs.host.activate("files");
    await settle();
    expect(page.tabs.shown.value).toBe("files");
    release();
    await replay;
    page.controller.value!.tabs.hide("files");
    await settle();

    expect(page.tabs.shown.value).toBe("activity");
  });

  it("stays put when a later replay reorders the strip and the address names no tab", async () => {
    let reorder = false;
    registerRecordPage("CRM Deal", {
      onRefresh: (api) => {
        if (reorder) api.tabs.order(["details"]);
      },
    });
    const page = makePage();
    await page.open();

    reorder = true;
    await page.controller.value!.refresh();
    await settle();

    expect(page.tabs.shown.value).toBe("activity");
    expect(page.route.query.tab).toBeUndefined();
  });

  it("opens a new page on the address alone, not on the last page's tab", async () => {
    registerRecordPage("CRM Deal", { onRefresh: (api) => api.tabs.order(["details"]) });
    const page = makePage();
    await page.open();
    expect(page.tabs.shown.value).toBe("details");

    resetRegistry();
    await page.open();

    expect(page.tabs.shown.value).toBe("activity");
  });

  it("gives no warning on a cold load whose `?tab=` names a hidden tab", async () => {
    registerRecordPage("CRM Deal", { onRefresh: (api) => api.tabs.hide("files") });
    const page = makePage({ tab: "files" });

    await page.open();

    expect(page.tabs.shown.value).toBe("activity");
    expect(warnings).toEqual([]);
  });
});

describe("the tab events", () => {
  it("fires `onTabChange` between shown tabs with the page alone, reading `active`", async () => {
    const seen: unknown[][] = [];
    registerRecordPage("CRM Deal", {
      onTabChange: (api, row) => void seen.push([api.tabs.active, row]),
    });
    const page = makePage();
    await page.open();

    await page.tabs.host.activate("emails");
    await settle();

    expect(seen).toEqual([["emails", undefined]]);
  });

  it("never fires on first paint, even for a tab the first replay activates", async () => {
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (api) => api.tabs.activate("files"),
      onTabChange: (api) => void seen.push(api.tabs.active),
    });
    const page = makePage();

    await page.open();

    expect(page.route.query.tab).toBe("files");
    expect(page.tabs.shown.value).toBe("files");
    expect(seen).toEqual([]);
  });

  it("fires for a script's `activate` in a later replay", async () => {
    let move = false;
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (api) => {
        if (move) api.tabs.activate("files");
      },
      onTabChange: (api) => void seen.push(api.tabs.active),
    });
    const page = makePage();
    await page.open();

    move = true;
    await page.controller.value!.refresh();
    await settle();

    expect(seen).toEqual(["files"]);
  });

  it("fires when a script hides the reader's tab, and warns", async () => {
    let hide = false;
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (api) => {
        if (hide) api.tabs.hide("files");
      },
      onTabChange: (api) => void seen.push(api.tabs.active),
    });
    const page = makePage({ tab: "files" });
    await page.open();

    hide = true;
    await page.controller.value!.refresh();
    await settle();

    expect(seen).toEqual(["activity"]);
    expect(warnings.some((message) => message.includes('hide("files")'))).toBe(true);
  });

  it("fires `onFormTabChange` between two form tabs on Details, never on the first", async () => {
    const seen: unknown[] = [];
    registerRecordPage("CRM Deal", { onFormTabChange: (_, row) => void seen.push(row) });
    const page = makePage({ tab: "details" });
    await page.open();

    page.formTab.value = "lead_details";
    await settle();
    page.formTab.value = "products";
    await settle();

    expect(seen).toEqual([undefined]);
  });

  it("never fires `onFormTabChange` while the reader is off Details, nor on the way back", async () => {
    let fired = 0;
    registerRecordPage("CRM Deal", { onFormTabChange: () => void (fired += 1) });
    const page = makePage({ tab: "details" });
    await page.open();
    page.formTab.value = "lead_details";
    await settle();

    await page.tabs.host.activate("activity");
    page.formTab.value = "products";
    await settle();
    await page.tabs.host.activate("details");
    await settle();

    expect(fired).toBe(0);
  });

  it("reads `page.form.tabs.active` as the form's tab on Details and as nothing elsewhere", async () => {
    const page = makePage({ tab: "details" });
    await page.open();
    page.formTab.value = "lead_details";
    await settle();
    const formTabs = page.controller.value!.page.form.tabs;
    expect(formTabs.active).toBe("lead_details");

    await page.tabs.host.activate("activity");
    await settle();

    expect(formTabs.active).toBe("");
  });
});
