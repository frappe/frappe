// The compatibility mechanisms as executable claims: a removed name is answered
// by name, and a name that never existed is left alone.
import { beforeEach, describe, expect, it, vi } from "vitest";

const { call, toast } = vi.hoisted(() => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
}));

vi.mock("frappe-ui", () => ({
  call,
  toast,
  dialog: { confirm: vi.fn(), danger: vi.fn() },
}));

import {
  resetRemovalNotices,
  withRemovals,
  type Removal,
} from "../pageCompatibility";
import { loadPageScripts, resetPageScripts } from "../pageScripts";
import { resetCustomizationErrorReports } from "../reportError";

const REPORT_METHOD =
  "frappe.desk.customization_error.report_customization_error";

const tombstoned: Removal = {
  path: "dialog.prompt",
  removedIn: "0.3.0",
  instead: "page.dialog.form",
  stage: "tombstone",
};

const gone: Removal = {
  path: "refreshAll",
  removedIn: "0.2.0",
  instead: "page.refresh",
  stage: "gone",
};

function makePage() {
  return {
    doctype: "CRM Deal",
    refresh: () => "refreshed",
    dialog: { form: () => "form" },
  } as any;
}

/** The tier's fetch is what carries whether this session may write scripts. */
async function withEditorPermission(canWrite: boolean) {
  call.mockResolvedValue({ scripts: [], can_write: canWrite });
  await loadPageScripts("CRM Deal");
  call.mockClear();
}

describe("removals", () => {
  beforeEach(() => {
    resetRemovalNotices();
    resetPageScripts();
    resetCustomizationErrorReports();
    call.mockReset();
    call.mockResolvedValue({});
    toast.error.mockReset();
  });

  it("installs nothing at all while nothing has been removed", () => {
    const page = makePage();
    expect(withRemovals(page, [])).toBe(page);
  });

  it("keeps a removed verb as a thrower naming the removal and its replacement", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const page = withRemovals(makePage(), [tombstoned]);

    expect(typeof page.dialog.prompt).toBe("function");
    expect(() => page.dialog.prompt()).toThrow(
      "page.dialog.prompt was removed in 0.3.0 — use page.dialog.form",
    );
  });

  it("hands the same function back on every read", () => {
    const page = withRemovals(makePage(), [tombstoned]);
    expect(page.dialog.prompt).toBe(page.dialog.prompt);
  });

  it("leaves every other member of a guarded object alone", () => {
    const page = withRemovals(makePage(), [tombstoned]);

    expect(page.doctype).toBe("CRM Deal");
    expect(page.refresh()).toBe("refreshed");
    expect(page.dialog.form()).toBe("form");
  });

  it("files an Error Log row for a hit, and toasts an author who can edit scripts", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    await withEditorPermission(true);
    const page = withRemovals(makePage(), [tombstoned]);

    expect(() => page.dialog.prompt()).toThrow();

    expect(call).toHaveBeenCalledWith(REPORT_METHOD, expect.anything());
    expect(call.mock.calls[0][1].event).toBe("removed:dialog.prompt");
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("removed in 0.3.0"),
    );
  });

  it("still files the row for a reader who cannot edit scripts, but does not toast them", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    await withEditorPermission(false);
    const page = withRemovals(makePage(), [tombstoned]);

    expect(() => page.dialog.prompt()).toThrow();

    expect(call).toHaveBeenCalledWith(REPORT_METHOD, expect.anything());
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("toasts once per script per session, however often the verb is reached for", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    await withEditorPermission(true);
    const page = withRemovals(makePage(), [tombstoned]);

    for (let attempt = 0; attempt < 3; attempt++)
      expect(() => page.dialog.prompt()).toThrow();

    expect(toast.error).toHaveBeenCalledTimes(1);
  });

  it("warns once and reads undefined for a removal past its tombstone", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const page = withRemovals(makePage(), [gone]);

    expect(page.refreshAll).toBeUndefined();
    expect(page.refreshAll).toBeUndefined();

    expect(warn).toHaveBeenCalledTimes(1);
    expect(warn).toHaveBeenCalledWith(
      expect.stringContaining("page.refreshAll, removed in 0.2.0"),
    );
    warn.mockRestore();
  });

  it("says nothing about a name that never existed — that probe is the documented idiom", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const page = withRemovals(makePage(), [tombstoned, gone]);

    expect(page.neverWasAVerb).toBeUndefined();
    expect(page.dialog.neverWasAVerb).toBeUndefined();

    expect(warn).not.toHaveBeenCalled();
    warn.mockRestore();
  });
});
