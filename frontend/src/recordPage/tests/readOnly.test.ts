// The outbound half of the compatibility policy (wayfinder ticket 47) as
// executable claims: nothing `page` hands back may be mutated into shared
// state, the refusal names the path and the supported verb, and `page.doc` is
// the one exception.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

const state = vi.hoisted(() => ({ roles: null as string[] | null }));

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
  createResource: (options: any) => ({
    get data() {
      return options.url.endsWith("get_current_user_roles")
        ? state.roles
        : null;
    },
    loading: false,
    fetch() {},
    reload() {},
  }),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { withRunningSource } from "../context";
import { loadPageScripts, resetPageScripts } from "../pageScripts";
import { readOnly } from "../readOnly";
import { resetRegistry } from "../registry";
import { resetCustomizationErrorReports } from "../reportError";
import { resetUserRoles } from "@framework/ui/composables/useUserRoles";
import { call as mockedCall, toast as mockedToast } from "frappe-ui";

const REPORT_METHOD =
  "frappe.desk.customization_error.report_customization_error";

const META = {
  name: "CRM Deal",
  fields: [
    { fieldname: "status", fieldtype: "Select", hidden: 0 },
    { fieldname: "qty", fieldtype: "Int", hidden: 0 },
  ],
};

const ADVICE = { path: "page.meta", instead: "page.fields.update(...)" };

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open" }),
    saved: ref({ status: "Open" }),
    meta: ref(structuredClone(META)),
    perms: () => ({ read: 1, write: 1 }),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
}

/** The tier's fetch is what carries whether this session may write scripts. */
async function withEditorPermission(canWrite: boolean) {
  (mockedCall as any).mockResolvedValue({ scripts: [], can_write: canWrite });
  await loadPageScripts("CRM Deal");
  (mockedCall as any).mockClear();
}

function reset() {
  state.roles = null;
  resetRegistry();
  resetUserRoles();
  resetPageScripts();
  resetCustomizationErrorReports();
  (mockedCall as any).mockReset();
  (mockedCall as any).mockResolvedValue({});
  (mockedToast as any).error.mockReset();
  vi.spyOn(console, "error").mockImplementation(() => {});
}

describe("readOnly", () => {
  beforeEach(reset);

  it("refuses a nested write, naming the path it was reached through", () => {
    const meta = readOnly(structuredClone(META), ADVICE);

    expect(() => {
      meta.fields[1].hidden = 1;
    }).toThrow("page.meta.fields[1].hidden is read-only");
  });

  it("names the supported verb, so the refusal is a redirect and not a removal", () => {
    const meta = readOnly(structuredClone(META), ADVICE);

    expect(() => {
      meta.fields[1].hidden = 1;
    }).toThrow("use page.fields.update(...)");
  });

  it("refuses a delete and a defineProperty, not only an assignment", () => {
    const meta = readOnly(structuredClone(META), ADVICE);

    expect(() => {
      delete (meta.fields[0] as any).hidden;
    }).toThrow("page.meta.fields[0].hidden is read-only");
    expect(() =>
      Object.defineProperty(meta.fields[0], "hidden", { value: 1 }),
    ).toThrow("page.meta.fields[0].hidden is read-only");
  });

  it("hands back the same wrapper for the same object, so identity holds", () => {
    const meta = readOnly(structuredClone(META), ADVICE);

    expect(meta.fields[0]).toBe(meta.fields[0]);
    expect(meta.fields.indexOf(meta.fields[0])).toBe(0);
  });

  it("leaves every read alone — find, filter, map and spread all still work", () => {
    const meta = readOnly(structuredClone(META), ADVICE);

    expect(meta.name).toBe("CRM Deal");
    expect(
      meta.fields.find((one: any) => one.fieldname === "qty"),
    ).toBeTruthy();
    expect(meta.fields.map((one: any) => one.fieldname)).toEqual([
      "status",
      "qty",
    ]);
    expect([...meta.fields]).toHaveLength(2);
    expect(Object.keys(meta)).toEqual(["name", "fields"]);
  });

  it("lets a script that wants to mutate copy first", () => {
    const meta = readOnly(structuredClone(META), ADVICE);
    const copy = meta.fields.map((one: any) => ({ ...one }));

    copy[0].hidden = 1;

    expect(copy[0].hidden).toBe(1);
    expect(meta.fields[0].hidden).toBe(0);
  });

  // A Proxy `get` must hand back a non-configurable, non-writable property
  // exactly as the target holds it. Deep-freezing meta at source is still on the
  // table (ticket 47 §1); without this, the day it lands every read throws.
  it("reads a frozen property without the engine refusing the read", () => {
    const frozen = { fields: Object.freeze([{ fieldname: "qty" }]) };
    const held = readOnly(frozen as any, ADVICE);

    expect(() => held.fields[0]).not.toThrow();
    expect(held.fields[0].fieldname).toBe("qty");
  });

  it("is idempotent — wrapping a wrapper hands the same wrapper back", () => {
    const once = readOnly(structuredClone(META), ADVICE);
    const twice = readOnly(once, ADVICE);

    expect(twice).toBe(once);
  });

  it("wraps nothing that is not a plain object or an array", () => {
    const when = new Date();
    const held = readOnly({ when, count: 3 } as any, ADVICE);

    expect(held.when).toBe(when);
    expect(held.when.getFullYear()).toBe(when.getFullYear());
    expect(held.count).toBe(3);
  });
});

describe("page.roles", () => {
  beforeEach(reset);

  it("refuses push — the write that corrupts the session-global array", () => {
    state.roles = ["Sales User"];
    const { page } = createRecordPage(makeHost());

    expect(() => page.roles.push("System Manager")).toThrow(
      "page.roles[1] is read-only",
    );
    expect(state.roles).toEqual(["Sales User"]);
  });

  it("refuses sort, which writes through indices like every array mutator", () => {
    state.roles = ["Sales User", "Accounts User"];
    const { page } = createRecordPage(makeHost());

    expect(() => page.roles.sort()).toThrow("is read-only");
    expect(state.roles).toEqual(["Sales User", "Accounts User"]);
  });

  it("refuses setPrototypeOf, the mutation that never reaches the set trap", () => {
    state.roles = ["Sales User"];
    const { page } = createRecordPage(makeHost());

    expect(() =>
      Object.setPrototypeOf(page.roles, { includes: () => true }),
    ).toThrow("page.roles's prototype is read-only");
    expect(state.roles!.includes("System Manager")).toBe(false);
  });

  it("refuses freeze, which would lock the shared array non-extensible", () => {
    state.roles = ["Sales User"];
    const { page } = createRecordPage(makeHost());

    expect(() => Object.freeze(page.roles)).toThrow(
      "page.roles's extensibility is read-only",
    );
    expect(Object.isFrozen(state.roles)).toBe(false);
  });

  it("still reads, so a copy sorts fine", () => {
    state.roles = ["Sales User", "Accounts User"];
    const { page } = createRecordPage(makeHost());

    expect([...page.roles].sort()).toEqual(["Accounts User", "Sales User"]);
  });
});

describe("page.meta and page.perms at the door", () => {
  beforeEach(reset);

  it("refuses a write to the cached meta that outlives this record", () => {
    const host = makeHost();
    const { page } = createRecordPage(host);

    expect(() => {
      page.meta.fields[1].hidden = 1;
    }).toThrow("page.meta.fields[1].hidden is read-only");
    expect(host.meta.value.fields[1].hidden).toBe(0);
  });

  it("refuses a write to the memoised rights view shared by every source", () => {
    const { page } = createRecordPage(makeHost());

    expect(() => {
      (page.perms as any).write = 1;
    }).toThrow("page.perms.write is read-only");
  });

  it("keeps page.doc writable, because mutating the document is the API", () => {
    const { page } = createRecordPage(makeHost());

    page.doc.status = "Won";

    expect(page.doc.status).toBe("Won");
  });
});

// The saved mirror (wayfinder ticket 46): the v2 answer to "what was the
// previous value", and one letter away from the draft you may edit.
describe("page.saved", () => {
  beforeEach(reset);

  it("is the document as the server last showed it, defined before any edit", () => {
    const { page } = createRecordPage(makeHost());

    page.doc.status = "Won";

    expect(page.saved.status).toBe("Open");
    expect(page.saved.status !== page.doc.status).toBe(true);
  });

  it("refuses a write, and points at page.doc — the plausible typo", () => {
    const host = makeHost();
    const { page } = createRecordPage(host);

    expect(() => {
      page.saved.status = "Won";
    }).toThrow("page.saved.status is read-only — use page.doc");
    expect(host.saved.value.status).toBe("Open");
  });

  it("tracks the baseline the host repaints after a save", () => {
    const host = makeHost();
    const { page } = createRecordPage(host);

    host.saved.value = { status: "Won" };

    expect(page.saved.status).toBe("Won");
  });
});

describe("the refusal reports on the tombstone channel", () => {
  beforeEach(reset);

  it("files an Error Log row and toasts an author who can edit scripts", async () => {
    await withEditorPermission(true);
    const { page } = createRecordPage(makeHost());

    await withRunningSource("page-script:products", async () => {
      expect(() => {
        page.meta.fields[0].hidden = 1;
      }).toThrow();
    });

    expect(mockedCall).toHaveBeenCalledWith(REPORT_METHOD, expect.anything());
    const payload = (mockedCall as any).mock.calls[0][1];
    expect(payload.source).toBe("page-script:products");
    expect(payload.event).toBe("readonly:page.meta");
    expect(payload.message).toContain("page.meta.fields[0].hidden");
    expect((mockedToast as any).error).toHaveBeenCalledWith(
      expect.stringContaining("read-only"),
    );
  });

  it("files once per member per script, however many rows it walks", async () => {
    await withEditorPermission(true);
    const { page } = createRecordPage(makeHost());

    await withRunningSource("page-script:products", async () => {
      for (const field of page.meta.fields)
        expect(() => {
          field.hidden = 1;
        }).toThrow();
    });

    const reports = (mockedCall as any).mock.calls.filter(
      ([method]: [string]) => method === REPORT_METHOD,
    );
    expect(reports).toHaveLength(1);
    expect((mockedToast as any).error).toHaveBeenCalledTimes(1);
  });

  it("still files the row for a reader who cannot edit scripts, without toasting", async () => {
    await withEditorPermission(false);
    const { page } = createRecordPage(makeHost());

    expect(() => {
      page.meta.fields[0].hidden = 1;
    }).toThrow();

    expect(mockedCall).toHaveBeenCalledWith(REPORT_METHOD, expect.anything());
    expect((mockedToast as any).error).not.toHaveBeenCalled();
  });
});
