// A submitted record reads as read-only except `allow_on_submit` fields; a cancelled one is read-only throughout.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { nextTick, ref } from "vue";

const fake = vi.hoisted(() => ({ getMeta: vi.fn(), runMethod: vi.fn(), access: vi.fn() }));

vi.mock("frappe-ui", () => ({ toast: { success: vi.fn(), error: vi.fn() }, frappeRequest: vi.fn() }));
vi.mock("@framework/ui/api", () => ({ getMeta: fake.getMeta, runMethod: fake.runMethod }));

import { resolveLayout } from "@framework/ui/FormLayout";
import { resetDoctypeMeta } from "@framework/ui/useDoctypeMeta";
import { resetFormLayouts, useFormLayout } from "@/recordPage/formLayoutSource/useFormLayout";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { accessAtDocstatus } from "../formLayoutSource/fieldAccess";

const FIELDS = [
  { fieldname: "posting_date", fieldtype: "Date", label: "Posting Date" },
  { fieldname: "remarks", fieldtype: "Small Text", label: "Remarks", allow_on_submit: 1 },
  { fieldname: "items", fieldtype: "Table", label: "Items", options: "Row", allow_on_submit: 1 },
  { fieldname: "taxes", fieldtype: "Table", label: "Taxes", options: "Row" },
  { fieldname: "details", fieldtype: "Section Break", label: "Details" },
];
const TREE = [
  { name: "details", label: "Details", sections: [{ columns: [{ fields: FIELDS.map((f) => f.fieldname) }] }] },
];

describe("accessAtDocstatus", () => {
  const field = (extra = {}) => ({ fieldtype: "Data", ...extra });

  it("leaves a draft alone", () => {
    expect(accessAtDocstatus("write", field(), 0)).toBe("write");
    expect(accessAtDocstatus("write", field(), undefined)).toBe("write");
  });

  it("keeps only allow_on_submit fields writable once submitted", () => {
    expect(accessAtDocstatus("write", field(), 1)).toBe("read");
    expect(accessAtDocstatus("write", field({ allow_on_submit: 1 }), 1)).toBe("write");
  });

  it("makes every field read-only once cancelled, allow_on_submit or not", () => {
    expect(accessAtDocstatus("write", field({ allow_on_submit: 1 }), 2)).toBe("read");
  });

  it("never lifts a permlevel denial", () => {
    expect(accessAtDocstatus("read", field({ allow_on_submit: 1 }), 1)).toBe("read");
    expect(accessAtDocstatus("none", field({ allow_on_submit: 1 }), 1)).toBe("none");
  });

  it("leaves a field with no value (a button, a section) as it was", () => {
    expect(accessAtDocstatus("write", { fieldtype: "Button" }, 1)).toBe("write");
    expect(accessAtDocstatus("write", { fieldtype: "Section Break" }, 2)).toBe("write");
  });

  it("lets a Table follow its own allow_on_submit", () => {
    expect(accessAtDocstatus("write", { fieldtype: "Table", allow_on_submit: 1 }, 1)).toBe("write");
    expect(accessAtDocstatus("write", { fieldtype: "Table" }, 1)).toBe("read");
  });
});

function makeHost(docstatus: number): RecordPageHost {
  return {
    app: "frappe",
    doctype: "Journal Entry",
    docname: "JV-1",
    doc: ref({ docstatus }),
    saved: ref({ docstatus }),
    meta: ref({ name: "Journal Entry", fields: FIELDS }),
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

describe("page.fieldAccess on a submitted record", () => {
  it.each([
    [0, { posting_date: "write", remarks: "write", items: "write", taxes: "write" }],
    [1, { posting_date: "read", remarks: "write", items: "write", taxes: "read" }],
    [2, { posting_date: "read", remarks: "read", items: "read", taxes: "read" }],
  ])("docstatus %i", (docstatus, expected) => {
    const { page } = createRecordPage(makeHost(docstatus));
    const got = Object.fromEntries(Object.keys(expected).map((name) => [name, page.fieldAccess(name)]));
    expect(got).toEqual(expected);
  });
});

async function settle() {
  for (let turn = 0; turn < 3; turn++) {
    await Promise.resolve();
    await nextTick();
  }
}

function nodesOf(layout: any) {
  const nodes: any[] = [];
  const walk = (value: any) => {
    if (Array.isArray(value)) return value.forEach(walk);
    if (!value || typeof value !== "object") return;
    if (value.fieldname) nodes.push(value);
    Object.values(value).forEach(walk);
  };
  walk(layout);
  return nodes;
}

async function drawn(docstatus: number, overrides: Record<string, any> = {}, type: any = "Details") {
  const saved = ref<Record<string, any>>({ docstatus });
  const { layout } = useFormLayout({
    doctype: "Journal Entry",
    type,
    doc: saved,
    fallback: "meta",
    overrides: () => overrides,
  });
  await settle();
  return nodesOf(resolveLayout(layout.value, saved.value));
}

const readOnlyOf = (nodes: any[]) => Object.fromEntries(nodes.map((n) => [n.fieldname, Boolean(n.readOnly)]));

describe("the Details form on a submitted record", () => {
  beforeEach(() => {
    resetDoctypeMeta();
    resetFormLayouts();
    fake.getMeta.mockReset().mockResolvedValue({
      data: { name: "Journal Entry", fields: FIELDS },
      children: [
        {
          name: "Row",
          fields: [
            { fieldname: "qty", fieldtype: "Float" },
            { fieldname: "note", fieldtype: "Data", allow_on_submit: 1 },
          ],
        },
      ],
    });
    fake.runMethod.mockReset().mockResolvedValue({ data: { layouts: [], fallback: TREE } });
  });

  it.each([
    [0, { posting_date: false, remarks: false, items: false, taxes: false }],
    [1, { posting_date: true, remarks: false, items: false, taxes: true }],
    [2, { posting_date: true, remarks: true, items: true, taxes: true }],
  ])("draws docstatus %i", async (docstatus, expected) => {
    const read = readOnlyOf(await drawn(docstatus));
    expect(read).toMatchObject(expected);
  });

  it("locks a writable Table's cells that lack allow_on_submit", async () => {
    const read = readOnlyOf(await drawn(1));
    expect(read).toMatchObject({ qty: true, note: false });
    expect(readOnlyOf(await drawn(2)).note).toBe(true);
    expect(readOnlyOf(await drawn(0)).qty).toBe(false);
  });

  it("locks nothing in a New Record, whatever docstatus its opening values carry", async () => {
    const read = readOnlyOf(await drawn(1, {}, "New Record"));
    expect(read).toMatchObject({ posting_date: false, qty: false });
  });

  it("locks the form when the record is submitted after it opened", async () => {
    const saved = ref<Record<string, any>>({ docstatus: 0 });
    const { layout } = useFormLayout({ doctype: "Journal Entry", type: "Details", doc: saved, fallback: "meta" });
    await settle();
    expect(readOnlyOf(nodesOf(layout.value)).posting_date).toBe(false);

    saved.value = { docstatus: 1 };
    await settle();
    expect(readOnlyOf(nodesOf(layout.value)).posting_date).toBe(true);
  });

  it("refuses a script write that unlocks a locked field, with a warning", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const nodes = await drawn(1, { posting_date: { override: { readOnly: false } } });

    expect(readOnlyOf(nodes).posting_date).toBe(true);
    expect(warn.mock.calls.flat().join(" ")).toContain('on "posting_date"');
    warn.mockRestore();
  });
});
