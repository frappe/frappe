// `page.app` as executable claims: a script reads the app it runs in and cannot change it.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// The page only borrows `call` and `toast`; the real barrel drags icon plugins in.
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

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import type { RecordPageApi } from "../types";

function makeHost(app: string): RecordPageHost {
  return {
    app,
    doctype: "Contact",
    docname: "CONTACT-1",
    doc: ref({}),
    saved: ref({}),
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
  };
}

describe("page.app", () => {
  beforeEach(() => resetRegistry());

  it.each(["frappe", "crm"])("gives a script the app it runs in: %s", async (app) => {
    const seen: string[] = [];
    registerRecordPage("Contact", { onRefresh: (page: RecordPageApi) => void seen.push(page.app) });
    await createRecordPage(makeHost(app)).refresh();
    expect(seen).toEqual([app]);
  });

  it("refuses an assignment and keeps the app", () => {
    const { page } = createRecordPage(makeHost("crm"));
    expect(() => {
      (page as { app: string }).app = "frappe";
    }).toThrow(TypeError);
    expect(page.app).toBe("crm");
  });
});
