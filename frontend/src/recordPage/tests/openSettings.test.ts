// `page.openSettings`: the shell's `open_settings` act, held in a replay and quiet once the page has gone.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: { confirm: vi.fn(), danger: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
}));

import { acts } from "@/acts/dispatcher";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    app: "frappe",
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

let release = () => {};
afterEach(() => {
  release();
  vi.restoreAllMocks();
});

/** A shell surface holding only `shell.open_settings`; each run records the address it was given. */
function shellSettings() {
  const openSettings = vi.fn();
  release = acts.register({
    surfaces: {
      shell: () => [{ item: { name: "open_settings", run: (_shell, value) => openSettings(value) }, hidden: false }],
    },
    context: () => undefined,
    passes: () => false,
    settled: () => undefined,
    hold: async (work) => work(),
    failed: () => {},
  });
  return openSettings;
}

const address = (prefix?: string, pane?: string, block?: string) => [{ prefix, pane, block }];

describe("page.openSettings", () => {
  it("runs shell.open_settings with the address segments as given", () => {
    const openSettings = shellSettings();
    const { page } = createRecordPage(makeHost());

    page.openSettings("desk", "profile", "telephony");
    page.openSettings();

    expect(openSettings.mock.calls).toEqual([address("desk", "profile", "telephony"), address()]);
  });

  it("waits for the commit when called in a replay, and the last call wins", async () => {
    const openSettings = shellSettings();
    const controller = createRecordPage(makeHost());
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
    expect(openSettings.mock.calls).toEqual([address("desk", "system")]);
  });

  it("drops a call in the replay after a background read, with a warning", async () => {
    const openSettings = shellSettings();
    const controller = createRecordPage(makeHost());
    registerRecordPage("CRM Deal", { onRefresh: (page) => page.openSettings("desk", "profile") });
    await controller.refresh();

    await controller.refresh({ background: true });

    expect(openSettings.mock.calls).toEqual([address("desk", "profile")]);
    expect(warnings).toEqual([
      '[record-page] page.openSettings("desk", "profile") — it ran in the replay after a background read; nothing was opened.',
    ]);
  });

  it("opens nothing once the page has left", () => {
    const openSettings = shellSettings();
    const controller = createRecordPage(makeHost());
    controller.leave();

    controller.page.openSettings("desk");
    expect(openSettings).not.toHaveBeenCalled();
  });

  it("warns and opens nothing when no shell holds the act", async () => {
    const { page } = createRecordPage(makeHost());

    page.openSettings("desk", "profile");
    await Promise.resolve();
    expect(warnings.join("\n")).toContain(
      'page.openSettings("desk", "profile") — shell.open_settings: no surface holds this act now'
    );
  });
});
