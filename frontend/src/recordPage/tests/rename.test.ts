// `page.rename` hands the name and merge to the host's rename, and answers null where there is none.
import { describe, expect, it, vi } from "vitest";
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

function makeHost(rename?: RecordPageHost["rename"]): RecordPageHost {
  return {
    app: "frappe",
    doctype: "Note",
    docname: "N-1",
    doc: ref({}),
    saved: ref({}),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: () => {},
    save: async () => {},
    rename,
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
  };
}

describe("page.rename", () => {
  it("passes the name and merge to the host and resolves with the new name", async () => {
    const rename = vi.fn(async (name: string) => name);
    const { page } = createRecordPage(makeHost(rename));

    expect(await page.rename("N-2")).toBe("N-2");
    expect(await page.rename("N-3", { merge: true })).toBe("N-3");
    expect(rename.mock.calls).toEqual([
      ["N-2", false],
      ["N-3", true],
    ]);
  });

  it("resolves null with nothing to rename: a host with no saved record, or a page the reader left", async () => {
    expect(await createRecordPage(makeHost()).page.rename("N-2")).toBeNull();

    const rename = vi.fn(async (name: string) => name);
    const controller = createRecordPage(makeHost(rename));
    controller.leave();
    expect(await controller.page.rename("N-2")).toBeNull();
    expect(rename).not.toHaveBeenCalled();
  });
});
