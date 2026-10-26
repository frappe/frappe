// `page.openSettings`: the shell's settings act, held in a replay and quiet once the page has gone.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: { confirm: vi.fn(), danger: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
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
}

const warnings: string[] = [];

beforeEach(() => {
  resetRegistry();
  warnings.length = 0;
  vi.spyOn(console, "warn").mockImplementation((message) => void warnings.push(String(message)));
});

afterEach(() => vi.restoreAllMocks());

describe("page.openSettings", () => {
  it("hands the shell the address segments as given", () => {
    const openSettings = vi.fn();
    const { page } = createRecordPage(makeHost({ openSettings }));

    page.openSettings("crm", "general", "telephony");
    page.openSettings();

    expect(openSettings.mock.calls).toEqual([["crm", "general", "telephony"], []]);
  });

  it("waits for the commit when called in a replay, and the last call wins", async () => {
    const openSettings = vi.fn();
    const controller = createRecordPage(makeHost({ openSettings }));
    let seen: unknown[] = [];
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => {
        page.openSettings("desk", "profile");
        page.openSettings("desk", "system");
        seen = [...openSettings.mock.calls];
      },
    });
    await controller.refresh();

    expect(seen).toEqual([]);
    expect(openSettings.mock.calls).toEqual([["desk", "system"]]);
  });

  it("drops a call in the replay after a background read, with a warning", async () => {
    const openSettings = vi.fn();
    const controller = createRecordPage(makeHost({ openSettings }));
    registerRecordPage("CRM Deal", { onRefresh: (page) => page.openSettings("desk", "profile") });
    await controller.refresh();

    await controller.refresh({ background: true });

    expect(openSettings.mock.calls).toEqual([["desk", "profile"]]);
    expect(warnings).toEqual([
      '[record-page] page.openSettings("desk", "profile") — it ran in the replay after a background read; nothing was opened.',
    ]);
  });

  it("opens nothing once the page has left", () => {
    const openSettings = vi.fn();
    const controller = createRecordPage(makeHost({ openSettings }));
    controller.leave();

    controller.page.openSettings("desk");
    expect(openSettings).not.toHaveBeenCalled();
  });

  it("warns and opens nothing on a host with no settings act", () => {
    const { page } = createRecordPage(makeHost());

    page.openSettings("desk", "profile");
    expect(warnings.join("\n")).toContain(
      'page.openSettings("desk", "profile") — this host opens no settings'
    );
  });
});
