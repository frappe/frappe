// The record strip's host: the four built-ins, the `?tab=` rule, and when each tab event fires.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, reactive, ref, shallowRef } from "vue";

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
import { Surface } from "@/recordPage/surface";
import { TAB_ITEM_KEYS, type TabItem } from "@/recordPage/types";
import {
  recordTabBuiltins,
  RecordTabsHost,
  watchShownTab,
  watchTabEvents,
} from "../recordTabs";

/** A route and a router whose `replace` lands on the next tick, as vue-router's does. */
function makeAddress(query: Record<string, string> = {}) {
  const route = reactive({ query: { ...query } as Record<string, any> });
  const replace = vi.fn(async (to: { query: Record<string, any> }) => {
    await Promise.resolve();
    route.query = to.query;
  });
  return { route, router: { replace } as any };
}

function makeHost(query: Record<string, string> = {}) {
  const { route, router } = makeAddress(query);
  const tabs = new Surface<TabItem>({ surface: "tabs", keys: TAB_ITEM_KEYS });
  tabs.provideBuiltins(recordTabBuiltins);
  const host = new RecordTabsHost(route as any, router, () => tabs);
  return { host, tabs, route, router };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => warnings.push(message));
});

describe("the built-ins", () => {
  it("seeds four tabs in order, Activity first", () => {
    expect(recordTabBuiltins().map((tab) => tab.name)).toEqual([
      "activity",
      "emails",
      "files",
      "details",
    ]);
  });
});

describe("which tab shows", () => {
  it("is the address's tab while it is visible", () => {
    expect(makeHost({ tab: "files" }).host.active()).toBe("files");
  });

  it("is the first visible tab when the address names none", () => {
    expect(makeHost().host.active()).toBe("activity");
  });

  it("is the first visible tab for an unknown name, and the address is left alone", () => {
    const { host, route, router } = makeHost({ tab: "nope" });

    expect(host.active()).toBe("activity");
    expect(route.query.tab).toBe("nope");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("falls to the first visible tab when the address's tab is hidden, and returns on show", () => {
    const { host, tabs } = makeHost({ tab: "files" });

    tabs.hide("files");
    expect(host.active()).toBe("activity");
    tabs.show("files");
    expect(host.active()).toBe("files");
  });

  it("is empty with no visible tab", () => {
    const { host, tabs } = makeHost();

    tabs.clear();

    expect(host.active()).toBe("");
  });

  it("reads the replay in flight, so the first handler sees the tab the strip will show", () => {
    const { host, tabs } = makeHost();

    tabs.beginReplay();
    tabs.hide("activity");

    expect(tabs.visible()[0].name).toBe("activity");
    expect(host.active()).toBe("emails");
  });
});

describe("moving the reader", () => {
  it("replaces `?tab=` and keeps the other query keys", async () => {
    const { host, router } = makeHost({ view: "compact" });

    await host.activate("files");

    expect(router.replace).toHaveBeenCalledWith({ query: { view: "compact", tab: "files" } });
  });

  it("shows the new tab before the router settles", () => {
    const { host } = makeHost();

    void host.activate("files");

    expect(host.active()).toBe("files");
  });

  it("follows the address when it changes from outside", async () => {
    const { host, route } = makeHost();

    route.query = { tab: "emails" };
    await nextTick();

    expect(host.active()).toBe("emails");
  });
});

describe("a field focus", () => {
  it("brings Details forward first", async () => {
    const { host, router } = makeHost({ tab: "files" });

    await host.showDetails();

    expect(host.active()).toBe("details");
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it("leaves the address alone when the reader is on Details or Details is hidden", async () => {
    const onDetails = makeHost({ tab: "details" });
    const hidden = makeHost();
    hidden.tabs.hide("details");

    await onDetails.host.showDetails();
    await hidden.host.showDetails();

    expect(onDetails.router.replace).not.toHaveBeenCalled();
    expect(hidden.router.replace).not.toHaveBeenCalled();
  });
});

describe("the form strip's tab", () => {
  it("is the form's while the reader is on Details, and empty elsewhere", () => {
    expect(makeHost({ tab: "details" }).host.formTab("lead_details")).toBe("lead_details");
    expect(makeHost({ tab: "files" }).host.formTab("lead_details")).toBe("");
  });
});

describe("a hidden active tab", () => {
  it("warns with the tab's name", () => {
    const { host, tabs } = makeHost();

    tabs.hide("activity");
    host.warnIfHidden("activity");

    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toContain('page.tabs.hide("activity")');
  });

  it("does not warn for a visible or unknown tab", () => {
    const { host } = makeHost();

    host.warnIfHidden("activity");
    host.warnIfHidden("nope");

    expect(warnings).toEqual([]);
  });
});

describe("a move within one page", () => {
  function watchMoves() {
    const owner = shallowRef<object>({});
    const shown = ref("");
    const moves: [string, string][] = [];
    watchShownTab(
      () => owner.value,
      () => shown.value,
      (previous, next) => void moves.push([previous, next]),
    );
    return { owner, shown, moves };
  }

  it("is not the page's first tab", async () => {
    const { shown, moves } = watchMoves();

    shown.value = "activity";
    await nextTick();

    expect(moves).toEqual([]);
  });

  it("is a change between two tabs", async () => {
    const { shown, moves } = watchMoves();

    shown.value = "activity";
    await nextTick();
    shown.value = "files";
    await nextTick();

    expect(moves).toEqual([["activity", "files"]]);
  });

  it("is never a change across a new page", async () => {
    const { owner, shown, moves } = watchMoves();

    shown.value = "activity";
    await nextTick();
    owner.value = {};
    shown.value = "files";
    await nextTick();

    expect(moves).toEqual([]);
  });

  it("reports a move to no tab, so the host can warn", async () => {
    const { shown, moves } = watchMoves();

    shown.value = "activity";
    await nextTick();
    shown.value = "";
    await nextTick();

    expect(moves).toEqual([["activity", ""]]);
  });
});

describe("the tab events", () => {
  function makePage(query: Record<string, string> = {}) {
    const { route, router } = makeAddress(query);
    const controller = shallowRef<RecordPageController | null>(null);
    const host = new RecordTabsHost(route as any, router, () => controller.value?.tabs);
    controller.value = createRecordPage({
      doctype: "CRM Deal",
      docname: "CRM-DEAL-1",
      doc: ref({}),
      saved: ref({}),
      meta: ref(null),
      perms: () => ({}),
      isDirty: () => false,
      activeTab: () => host.active(),
      activateTab: (name) => void host.activate(name),
      save: async () => {},
      reload: async () => {},
      router,
    });
    controller.value.tabs.provideBuiltins(recordTabBuiltins);
    const formTab = ref("");
    const shown = () => (controller.value?.ready.value ? host.active() : "");
    watchTabEvents(host, () => controller.value, { tab: shown, formTab: () => formTab.value });
    return { controller, host, formTab, route };
  }

  async function settle() {
    for (let turn = 0; turn < 3; turn++) await nextTick();
  }

  it("fires `onTabChange` between shown tabs with the page alone, reading `active`", async () => {
    const seen: unknown[][] = [];
    registerRecordPage("CRM Deal", {
      onTabChange: (page, row) => void seen.push([page.tabs.active, row]),
    });
    const { controller, host } = makePage();
    await controller.value!.refresh();
    await settle();

    await host.activate("emails");
    await settle();

    expect(seen).toEqual([["emails", undefined]]);
  });

  it("never fires on first paint, even for a tab the first replay activates", async () => {
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => page.tabs.activate("files"),
      onTabChange: (page) => void seen.push(page.tabs.active),
    });
    const { controller, route } = makePage();

    await controller.value!.refresh();
    await settle();

    expect(route.query.tab).toBe("files");
    expect(seen).toEqual([]);
  });

  it("fires for a script's `activate` in a later replay", async () => {
    let move = false;
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        if (move) page.tabs.activate("files");
      },
      onTabChange: (page) => void seen.push(page.tabs.active),
    });
    const { controller } = makePage();
    await controller.value!.refresh();
    await settle();

    move = true;
    await controller.value!.refresh();
    await settle();

    expect(seen).toEqual(["files"]);
  });

  it("fires when a script hides the reader's tab, and warns", async () => {
    let hide = false;
    const seen: string[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        if (hide) page.tabs.hide("files");
      },
      onTabChange: (page) => void seen.push(page.tabs.active),
    });
    const { controller } = makePage({ tab: "files" });
    await controller.value!.refresh();
    await settle();

    hide = true;
    await controller.value!.refresh();
    await settle();

    expect(seen).toEqual(["activity"]);
    expect(warnings.some((message) => message.includes('hide("files")'))).toBe(true);
  });

  it("fires `onFormTabChange` between two form tabs, never on the first", async () => {
    const seen: unknown[] = [];
    registerRecordPage("CRM Deal", {
      onFormTabChange: (page, row) => void seen.push(row),
    });
    const { formTab } = makePage();

    formTab.value = "lead_details";
    await settle();
    formTab.value = "products";
    await settle();

    expect(seen).toEqual([undefined]);
  });
});
