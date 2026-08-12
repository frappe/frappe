// The event vocabulary's firing semantics (wayfinder ticket 14) as executable claims.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

// The page only borrows `call` and `toast`; the real barrel drags icon plugins in.
vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import { withRegisteringSource } from "../context";

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    meta: ref(null),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
}

describe("fireEvent", () => {
  beforeEach(() => resetRegistry());

  it("propagates a before_save throw so the host can abort the save", async () => {
    registerRecordPage("CRM Deal", {
      before_save: () => {
        throw new Error("Amount required");
      },
    });
    const controller = createRecordPage(makeHost());
    await expect(controller.fireEvent("before_save")).rejects.toThrow(
      "Amount required",
    );
  });

  it("stops later before_save handlers once one vetoes", async () => {
    const ran: string[] = [];
    await withRegisteringSource("first", async () => {
      registerRecordPage("CRM Deal", {
        before_save: () => {
          ran.push("first");
          throw new Error("veto");
        },
      });
    });
    await withRegisteringSource("second", async () => {
      registerRecordPage("CRM Deal", { before_save: () => ran.push("second") });
    });
    const controller = createRecordPage(makeHost());
    await expect(controller.fireEvent("before_save")).rejects.toThrow("veto");
    expect(ran).toEqual(["first"]);
  });

  it("isolates a throw from every other event", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const ran: string[] = [];
    await withRegisteringSource("first", async () => {
      registerRecordPage("CRM Deal", {
        refresh: () => {
          throw new Error("broken script");
        },
      });
    });
    await withRegisteringSource("second", async () => {
      registerRecordPage("CRM Deal", { refresh: () => ran.push("second") });
    });
    const controller = createRecordPage(makeHost());
    await controller.refresh();
    expect(ran).toEqual(["second"]);
    expect(errors).toHaveBeenCalled();
    errors.mockRestore();
  });
});

describe("page.tabs.active", () => {
  it("reads the tab the host's strip resolves", () => {
    resetRegistry();
    const controller = createRecordPage(
      makeHost({ activeTab: () => "audit_log" }),
    );
    expect(controller.page.tabs.active).toBe("audit_log");
  });
});

describe("unknown handler keys", () => {
  beforeEach(() => resetRegistry());

  const fields = [
    { fieldname: "status", fieldtype: "Select" },
    { fieldname: "items", fieldtype: "Table" },
  ];

  it("warns once, after meta arrives, for a key that will never fire", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", { after_svae: () => {} });
    const meta = ref<any>(null);
    const controller = createRecordPage(makeHost({ meta }));
    await controller.refresh();
    meta.value = { fields };
    await controller.refresh();
    await controller.refresh();
    const typoWarnings = warnings.mock.calls.filter((call) =>
      String(call[0]).includes("after_svae"),
    );
    expect(typoWarnings).toHaveLength(1);
    warnings.mockRestore();
  });

  it("accepts events, fieldnames and child-table row events", async () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    registerRecordPage("CRM Deal", {
      refresh: () => {},
      before_save: () => {},
      after_save: () => {},
      on_tab_change: () => {},
      status: () => {},
      items: () => {},
      items_add: () => {},
      items_remove: () => {},
    });
    const controller = createRecordPage(makeHost({ meta: ref({ fields }) }));
    await controller.refresh();
    expect(warnings).not.toHaveBeenCalled();
    warnings.mockRestore();
  });
});
