// `onOpen` on a visit whose view the host puts back: its view acts are dropped, the rest land.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

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
      method === GET_CLIENT_SCRIPTS
        ? { data: { scripts: [], can_write: false } }
        : { data: null },
    ),
    getMeta: vi.fn(async () => ({ data: null })),
  };
});

import type { FormLayoutSchema } from "@framework/ui/components/FormLayout/types";
import { loadClientScripts, resetClientScripts } from "../clientScripts";
import { withRegisteringSource } from "../context";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers, PanelSectionItem, RecordPageApi } from "../types";

const RECORD_TABS = [
  { name: "details", label: "Details" },
  { name: "activity", label: "Activity" },
  { name: "files", label: "Files" },
];

const LAYOUT: FormLayoutSchema = [
  { name: "lead_details", label: "Lead Details", sections: [] },
  { name: "products", label: "Products", sections: [] },
];

const PANEL: PanelSectionItem[] = [{ name: "organization_section", label: "Organization" }];

/** The host's halves of every view act, recorded, not performed. */
function makePage(overrides: Partial<RecordPageHost> = {}) {
  const acts: string[] = [];
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref({ fields: [{ fieldname: "qty", fieldtype: "Int" }] }),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: (name) => void acts.push(`tab:${name}`),
    formLayout: () => LAYOUT,
    activeFormTab: () => "lead_details",
    activateFormTab: (identity) => void acts.push(`form tab:${identity}`),
    discloseSection: (name, open) => void acts.push(`${open ? "open" : "close"}:${name}`),
    focusField: (fieldname) => void acts.push(`focus:${fieldname}`),
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    sourcesReady: () => loadClientScripts("CRM Deal"),
    activityRows: () => [],
    scrollToActivity: async (key) => Boolean(acts.push(`scroll:${key}`)),
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    openWriter: (name) => void acts.push(`writer:${name}`),
    closeWriter: () => {},
    activeWriter: () => "",
    ...overrides,
  };
  const controller = createRecordPage(host);
  controller.tabs.provideBuiltins(() => RECORD_TABS as any[]);
  controller.panelSections.provideBuiltins(() => PANEL);
  controller.composer.provideBuiltins(() => [{ name: "comment", label: "Comment" }]);
  return { controller, acts };
}

/** A return visit: scripts are in, and `paintNow` runs `onOpen`. */
async function openPage(overrides: Partial<RecordPageHost> = {}) {
  await loadClientScripts("CRM Deal");
  const made = makePage(overrides);
  await vi.advanceTimersByTimeAsync(0);
  made.controller.paintNow();
  await vi.advanceTimersByTimeAsync(0);
  return made;
}

function register(handlers: AuthoredHandlers) {
  return withRegisteringSource("deal", async () => registerRecordPage("CRM Deal", handlers));
}

function viewActs(page: RecordPageApi) {
  page.tabs.activate("files");
  page.form.tabs.activate("products");
  page.panelSections.open("organization_section");
  page.panelSections.close("organization_section");
  page.fields.focus("qty");
  page.activity.scrollTo("row-1");
  page.composer.open("comment");
}

const LANDED = [
  "tab:files",
  "form tab:products",
  "close:organization_section",
  "focus:qty",
  "scroll:row-1",
  "writer:comment",
];

const REASON = "onOpen ran on a view the page restored";

const SKIPPED = [
  `[record-page] page.tabs.activate("files") — ${REASON}; the reader was not moved.`,
  `[record-page] page.form.tabs.activate("products") — ${REASON}; the reader was not moved.`,
  `[record-page] page.panelSections.open("organization_section") — ${REASON}; nothing was opened.`,
  `[record-page] page.panelSections.close("organization_section") — ${REASON}; nothing was shut.`,
  `[record-page] page.fields.focus("qty") — ${REASON}; the reader was not moved.`,
  `[record-page] page.activity.scrollTo("row-1") — ${REASON}; the reader was not moved.`,
  `[record-page] page.composer.open("comment") — ${REASON}; nothing was opened.`,
];

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetClientScripts();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message) => void warnings.push(String(message)));
  vi.spyOn(console, "error").mockImplementation(() => {});
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("onOpen on a visit whose view the host restores", () => {
  it("drops each of the seven view acts with a warning", async () => {
    await register({ onOpen: viewActs });

    const { acts } = await openPage({ restoresView: () => true });

    expect(acts).toEqual([]);
    expect(warnings).toEqual(SKIPPED);
  });

  it("still lands the other acts of the same onOpen", async () => {
    let active = "";
    await register({
      onOpen: (page: RecordPageApi) => {
        page.tabs.activate("files");
        page.tabs.hide("files");
        page.quickActions.add({ name: "mine", label: "Mine", run: () => {} });
        active = page.tabs.active;
      },
    });

    const { controller, acts } = await openPage({ restoresView: () => true });

    expect(acts).toEqual([]);
    expect(active).toBe("activity");
    expect(controller.tabs.visible().map((tab) => tab.name)).toEqual(["details", "activity"]);
    expect(controller.quickActions.has("mine")).toBe(true);
  });

  it("drops a view act onOpen makes after an await", async () => {
    await register({
      onOpen: async (page: RecordPageApi) => {
        await Promise.resolve();
        page.tabs.activate("files");
        page.composer.open("comment");
      },
    });

    const { acts } = await openPage({ restoresView: () => true });

    expect(acts).toEqual([]);
    expect(warnings).toEqual([SKIPPED[0], SKIPPED[6]]);
  });

  it.each([
    ["false", () => false],
    ["absent", undefined],
  ])("lands the view acts as today when restoresView is %s", async (_, restoresView) => {
    await register({ onOpen: viewActs });

    const { acts } = await openPage({ restoresView });

    expect(acts).toEqual(LANDED);
    expect(warnings).toEqual([]);
  });

  it("leaves onRefresh's view acts alone", async () => {
    await register({
      onRefresh: (page: RecordPageApi) => page.tabs.activate("files"),
    });

    const { acts } = await openPage({ restoresView: () => true });

    expect(acts).toEqual(["tab:files"]);
    expect(warnings).toEqual([]);
  });
});
