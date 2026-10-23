// `page.create`: the shell's Create, given only the values, and quiet once the page has gone.
import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  dialog: { confirm: vi.fn(), danger: vi.fn() },
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

import { createRecordPage, type RecordPageHost } from "../createRecordPage";

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

describe("page.create", () => {
  it("opens the host's Create with only the values, and resolves with its answer", async () => {
    const openCreate = vi.fn(async () => ({ name: "CONTACT-1" }));
    const { page } = createRecordPage(makeHost({ openCreate }));

    const created = await page.create("Contact", {
      values: { company: "Acme" },
      onSave: () => {},
    } as any);

    expect(openCreate).toHaveBeenCalledWith("Contact", { values: { company: "Acme" } });
    expect(created).toEqual({ name: "CONTACT-1" });
  });

  it("passes no values when the script gives none", async () => {
    const openCreate = vi.fn(async () => null);
    const { page } = createRecordPage(makeHost({ openCreate }));

    expect(await page.create("Contact")).toBeNull();
    expect(openCreate).toHaveBeenCalledWith("Contact", { values: undefined });
  });

  it("resolves null without opening once the page has left", async () => {
    const openCreate = vi.fn(async () => ({ name: "CONTACT-1" }));
    const controller = createRecordPage(makeHost({ openCreate }));
    controller.leave();

    expect(await controller.page.create("Contact", { values: { company: "Acme" } })).toBeNull();
    expect(openCreate).not.toHaveBeenCalled();
  });

  it("resolves null on a host with no Create", async () => {
    const { page } = createRecordPage(makeHost());

    expect(await page.create("Contact", { values: { company: "Acme" } })).toBeNull();
  });
});
