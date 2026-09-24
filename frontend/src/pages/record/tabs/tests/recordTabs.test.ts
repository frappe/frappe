// The record strip's host: the four built-ins, the `?tab=` rule, and when each tab event fires.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, reactive, ref, shallowRef, type EffectScope } from "vue";

import { Surface } from "@/recordPage/surface";
import { TAB_ITEM_KEYS, type TabItem } from "@/recordPage/types";
import { recordTabBuiltins, RecordTabsHost } from "../recordTabs";
import { watchShownTab } from "../useRecordTabs";

/** A route and a router whose `replace` lands on the next tick, as vue-router's does. */
function makeAddress(query: Record<string, string> = {}, hash = "") {
  const route = reactive({ query: { ...query } as Record<string, any>, hash });
  const replace = vi.fn(async (to: { query: Record<string, any>; hash?: string }) => {
    await Promise.resolve();
    route.query = to.query;
    route.hash = to.hash ?? "";
  });
  return { route, router: { replace } as any };
}

function makeHost(query: Record<string, string> = {}, hash = "") {
  const { route, router } = makeAddress(query, hash);
  const tabs = new Surface<TabItem>({ surface: "tabs", keys: TAB_ITEM_KEYS });
  tabs.provideBuiltins(recordTabBuiltins);
  const host = scope.run(() => new RecordTabsHost(route as any, router, () => tabs))!;
  return { host, tabs, route, router };
}

let warnings: string[];
let scope: EffectScope;

beforeEach(() => {
  warnings = [];
  scope = effectScope();
  vi.spyOn(console, "warn").mockImplementation((message: string) => warnings.push(message));
});

afterEach(() => {
  scope.stop();
  vi.restoreAllMocks();
});

describe("the built-ins", () => {
  it("seeds four tabs in order, Details first", () => {
    expect(recordTabBuiltins().map((tab) => tab.name)).toEqual([
      "details",
      "activity",
      "emails",
      "files",
    ]);
  });
});

describe("which tab shows", () => {
  it("is the address's tab while it is visible", () => {
    expect(makeHost({ tab: "files" }).host.active()).toBe("files");
  });

  it("is the first visible tab when the address names none", () => {
    expect(makeHost().host.active()).toBe("details");
  });

  it("is the first visible tab for an unknown name, and the address is left alone", () => {
    const { host, route, router } = makeHost({ tab: "nope" });

    expect(host.active()).toBe("details");
    expect(route.query.tab).toBe("nope");
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("falls to the first visible tab when the address's tab is hidden, and returns on show", () => {
    const { host, tabs } = makeHost({ tab: "files" });

    tabs.hide("files");
    expect(host.active()).toBe("details");
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
    tabs.hide("details");

    expect(tabs.visible()[0].name).toBe("details");
    expect(host.active()).toBe("activity");
    expect(host.shown()).toBe("details");
  });
});

describe("moving the reader", () => {
  it("replaces `?tab=` and keeps the other query keys", async () => {
    const { host, router } = makeHost({ view: "compact" });

    await host.activate("files");

    expect(router.replace).toHaveBeenCalledWith({
      query: { view: "compact", tab: "files" },
      hash: "",
    });
  });

  it("keeps the hash, so a dialog living there stays open", async () => {
    const { host, route } = makeHost({}, "#settings/desk/general");

    await host.activate("files");

    expect(route.hash).toBe("#settings/desk/general");
  });

  it("works when passed bare, as a template's event handler passes it", async () => {
    const { host, route } = makeHost();
    const { activate } = host;

    await activate("files");

    expect(route.query.tab).toBe("files");
  });

  it("logs a navigation a guard refuses by throwing, and keeps the reader's tab", async () => {
    const { host, router } = makeHost();
    const failure = new Error("guard threw");
    router.replace.mockRejectedValueOnce(failure);
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});

    await host.activate("files");

    expect(errors).toHaveBeenCalledWith(failure);
    expect(host.active()).toBe("files");
  });

  it("shows the new tab before the router settles", () => {
    const { host } = makeHost();

    void host.activate("files");

    expect(host.shown()).toBe("files");
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

    expect(await host.showDetails("amount")).toBe(true);

    expect(host.active()).toBe("details");
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it("claims focus for Details once, so the strip leaves focus to the field's own landing", async () => {
    const { host } = makeHost({ tab: "files" });

    await host.showDetails("amount");

    expect(host.claimsFocus("details")).toBe(true);
    expect(host.claimsFocus("details")).toBe(false);
  });

  it("drops the claim when another move comes first", async () => {
    const { host } = makeHost({ tab: "files" });
    void host.showDetails("amount");

    void host.activate("emails");

    expect(host.claimsFocus("details")).toBe(false);
  });

  it("leaves the address alone when the reader is already on Details", async () => {
    const { host, router } = makeHost({ tab: "details" });

    expect(await host.showDetails("amount")).toBe(true);
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("refuses with a warning when a script hid Details, and moves nobody", async () => {
    const { host, tabs, router } = makeHost({ tab: "files" });
    tabs.hide("details");

    expect(await host.showDetails("amount")).toBe(false);

    expect(host.shown()).toBe("files");
    expect(router.replace).not.toHaveBeenCalled();
    expect(warnings).toEqual([
      '[record-page] page.fields.focus("amount") — the Details tab is hidden, so the reader was not moved.',
    ]);
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
    host.warnIfHidden("activity", "emails");

    expect(warnings).toEqual([
      '[record-page] page.tabs.hide("activity") — the reader was on it, so they moved to the first visible tab.',
    ]);
  });

  it("says so when no tab is left to show", () => {
    const { host, tabs } = makeHost();

    tabs.hide("activity");
    host.warnIfHidden("activity", "");

    expect(warnings[0]).toContain("so no tab is left to show.");
  });

  it("does not warn for a visible or unknown tab", () => {
    const { host } = makeHost();

    host.warnIfHidden("activity", "emails");
    host.warnIfHidden("nope", "activity");

    expect(warnings).toEqual([]);
  });
});

describe("a move within one page", () => {
  function watchMoves() {
    const owner = shallowRef<object>({});
    const shown = ref("");
    const moves: [string, string][] = [];
    scope.run(() =>
      watchShownTab(
        () => owner.value,
        () => shown.value,
        (previous, next) => void moves.push([previous, next]),
      ),
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

