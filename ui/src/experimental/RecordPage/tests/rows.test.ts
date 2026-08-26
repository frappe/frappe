// `page.rows`, the row handle and the dotted vocabulary (wayfinder tickets 43, 45).
import { beforeEach, describe, expect, it, vi } from "vitest";
import { isRef, reactive, ref, toRaw } from "vue";

vi.mock("frappe-ui", () => ({
  call: vi.fn(),
  toast: { success: vi.fn(), error: vi.fn() },
  createResource: () => ({ data: null, loading: false, fetch() {}, reload() {} }),
  frappeRequest: vi.fn(),
}));

import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import { withRegisteringSource } from "../context";
import { resetCustomizationErrorReports } from "../reportError";
import { resetRowWarnings } from "../rows";
import { ROW_ID } from "../../../components/Fields/rowIdentity";
import type { RecordPageApi, PageRow } from "../types";

const CHILD_FIELDS = [
  { fieldname: "qty", fieldtype: "Int" },
  { fieldname: "rate", fieldtype: "Currency" },
  { fieldname: "amount", fieldtype: "Currency" },
];

const META = {
  fields: [
    { fieldname: "status", fieldtype: "Select" },
    { fieldname: "products", fieldtype: "Table", options: "Deal Product" },
  ],
};

function makeHost(overrides: Partial<RecordPageHost> = {}): RecordPageHost {
  return {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({
      status: "Open",
      products: [
        { name: "row-a", qty: 2, rate: 50 },
        { name: "row-b", qty: 1, rate: 10 },
      ],
    }),
    saved: ref({}),
    meta: ref(META),
    perms: () => ({}),
    isDirty: () => false,
    activeTab: () => "activity",
    activateTab: () => {},
    save: async () => {},
    reload: async () => {},
    router: {} as any,
    ...overrides,
  };
}

function makePage(overrides: Partial<RecordPageHost> = {}) {
  const host = makeHost(overrides);
  return { host, controller: createRecordPage(host) };
}

beforeEach(() => {
  // A second `spyOn` of a console method hands back the *same* mock, calls and
  // all, so a test that silences one must not leak into the next one's reading.
  vi.restoreAllMocks();
  resetRegistry();
  resetCustomizationErrorReports();
  resetRowWarnings();
});

describe("page.rows", () => {
  it("hands back a handle per row, in array order", () => {
    const { controller } = makePage();
    const rows = controller.page.rows("products");
    expect(rows).toHaveLength(2);
    expect(rows.map((row) => row.qty)).toEqual([2, 1]);
  });

  it("mints an id for a row a script pushed onto the doc itself", () => {
    const { host, controller } = makePage();
    host.doc.value.products.push({ qty: 7 });
    expect(controller.page.rows("products").at(-1)!.qty).toBe(7);
    expect(host.doc.value.products[2][ROW_ID]).toMatch(/^row-\d+$/);
  });

  it("dev-warns and answers empty for a fieldname that is not a child table", () => {
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { controller } = makePage();
    expect(controller.page.rows("status")).toEqual([]);
    expect(String(warnings.mock.calls[0][0])).toContain("not a child table");
    warnings.mockRestore();
  });

  // Without this `indexOf`, `includes` and every `===` a script writes are
  // quietly wrong, and a handler cannot find the row it was handed in the table.
  it("hands back the same handle for the same row, every time", () => {
    const { controller } = makePage();
    const rows = controller.page.rows("products");
    expect(controller.page.rows("products")[0]).toBe(rows[0]);
    expect(rows.indexOf(rows[1])).toBe(1);
  });

  // A script copying a row copies its `__row_id`; two rows on one key would read
  // as one, and a handle would write into whichever came first.
  it("re-mints a duplicated key rather than letting two rows alias", () => {
    const { host, controller } = makePage();
    const [original] = host.doc.value.products;
    delete original.name;
    host.doc.value.products.push({ ...original });
    const rows = controller.page.rows("products");
    expect(rows[0]).not.toBe(rows[2]);
    rows[2].qty = 99;
    expect(host.doc.value.products[0].qty).not.toBe(99);
    expect(host.doc.value.products[2].qty).toBe(99);
  });

  // 47's rule, and its exemption: pushing to the array is meaningless, while
  // writing through a handle is the whole point of having one.
  it("refuses a write to the array but not to a handle", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { controller } = makePage();
    const rows = controller.page.rows("products");
    expect(() => rows.push({} as PageRow)).toThrow("read-only");
    rows[0].qty = 9;
    expect(controller.page.doc.products[0].qty).toBe(9);
  });
});

describe("the handle re-finds its row on every access (ticket 43 §2)", () => {
  it("follows a reorder, because it never captured a position", () => {
    const { host, controller } = makePage();
    const first = controller.page.rows("products")[0];
    host.doc.value.products.reverse();
    expect(first.rate).toBe(50);
  });

  it("survives a save, which replaces every row object", () => {
    const { host, controller } = makePage();
    const row = controller.page.rows("products")[0];
    host.doc.value = JSON.parse(JSON.stringify(host.doc.value));
    row.qty = 4;
    expect(host.doc.value.products[0].qty).toBe(4);
  });

  it("writes what a v1 script writes, bare", () => {
    const { host, controller } = makePage();
    const row = controller.page.rows("products")[0];
    row.amount = row.qty * row.rate;
    expect(host.doc.value.products[0].amount).toBe(100);
  });

  it("throws on a removed row, naming the path — where v1 loses the write", () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    const { host, controller } = makePage();
    const row = controller.page.rows("products")[0];
    host.doc.value.products.shift();
    expect(() => {
      row.product_name = "Widget";
    }).toThrow("products.product_name");
    expect(() => row.qty).toThrow("no longer in the document");
    expect(String(errors.mock.calls[0][0])).toContain("has been removed");
    errors.mockRestore();
  });

  it("attributes the refusal to the source whose handler held the row", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    await withRegisteringSource("page-script:C22", async () => {
      registerRecordPage("CRM Deal", {
        products: {
          onAdd: (page: RecordPageApi, row: PageRow) => {
            page.doc.products.length = 0;
            row.qty = 1;
          },
        },
      });
    });
    const { controller } = makePage();
    await controller.fireEvent("products.onAdd", {
      parentfield: "products",
      key: "name:row-a",
    });
    expect(String(errors.mock.calls[0][0])).toContain("page-script:C22 reached");
    errors.mockRestore();
  });

  // Vue's own flags are plain strings, so the symbol test alone would let a
  // removed handle throw from inside a render effect.
  it("answers a probe rather than throwing on being looked at", () => {
    const { host, controller } = makePage();
    const row = controller.page.rows("products")[0];
    host.doc.value.products.shift();
    expect((row as any)[Symbol.toStringTag]).toBeUndefined();
    expect((row as any).__v_isRef).toBeUndefined();
    expect(isRef(row)).toBe(false);
    expect(toRaw(row)).toBe(row);
  });

  // The same stamp that keeps the outbound read-only guard off a handle: Vue
  // must not deep-proxy one either, or a write would land on a copy.
  it("is raw to Vue, so reactive() hands it back as itself", () => {
    const { controller } = makePage();
    const row = controller.page.rows("products")[0];
    expect(reactive({ row }).row).toBe(row);
  });

  it("spreads and enumerates as the row's own data", () => {
    const { controller } = makePage();
    const row = controller.page.rows("products")[0];
    expect({ ...row }).toEqual({ name: "row-a", qty: 2, rate: 50 });
    expect(Object.keys(row)).not.toContain("trigger");
  });
});

describe("row.trigger", () => {
  it("takes a bare fieldname and forms the dotted key itself", async () => {
    const seen: any[] = [];
    registerRecordPage("CRM Deal", {
      "products.rate": (page: RecordPageApi, row: PageRow) =>
        seen.push([page.doctype, row.rate]),
    });
    const { controller } = makePage();
    await controller.page.rows("products")[1].trigger("rate");
    expect(seen).toEqual([["CRM Deal", 10]]);
  });

  it("resolves only once the handlers have run, where v1 lets the promise escape", async () => {
    const order: string[] = [];
    registerRecordPage("CRM Deal", {
      "products.rate": async () => {
        await Promise.resolve();
        order.push("handler");
      },
    });
    const { controller } = makePage();
    await controller.page.rows("products")[0].trigger("rate");
    order.push("after");
    expect(order).toEqual(["handler", "after"]);
  });

  it("throws when the row it would trigger for is gone", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { host, controller } = makePage();
    const row = controller.page.rows("products")[0];
    host.doc.value.products.shift();
    expect(() => row.trigger("rate")).toThrow("no longer in the document");
  });

  // 45 §3 gives `.onRemove` no row, so a verb that could fire it from a live row
  // would hand a handler the grenade that decision exists to withhold.
  it("refuses the structural keys, a dotted argument and an unknown field", async () => {
    const fired: string[] = [];
    registerRecordPage("CRM Deal", {
      products: {
        onAdd: () => fired.push("add"),
        onRemove: () => fired.push("remove"),
        rate: () => fired.push("rate"),
      },
    });
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { controller } = makePage({ childFields: () => CHILD_FIELDS });
    const row = controller.page.rows("products")[0];
    await row.trigger("onAdd");
    await row.trigger("onRemove");
    await row.trigger("products.rate");
    await row.trigger("ratte");
    expect(fired).toEqual([]);
    expect(warnings.mock.calls).toHaveLength(4);
    await row.trigger("rate");
    expect(fired).toEqual(["rate"]);
    warnings.mockRestore();
  });

  // The whole reason the lifecycle keys are `on`-prefixed (ticket 54): `add` is
  // a legal, unreserved fieldname, so under the old spelling this row's own
  // field was unaddressable and `products.add` meant two different events.
  it("triggers a child field genuinely called add", async () => {
    const fired: string[] = [];
    registerRecordPage("CRM Deal", { products: { add: () => fired.push("add") } });
    const warnings = vi.spyOn(console, "warn").mockImplementation(() => {});
    const { controller } = makePage({
      childFields: () => [...CHILD_FIELDS, { fieldname: "add", fieldtype: "Check" }],
    });
    await controller.page.rows("products")[0].trigger("add");
    expect(fired).toEqual(["add"]);
    expect(warnings).not.toHaveBeenCalled();
    warnings.mockRestore();
  });

  // The verb wins the namespace; the field stays reachable through `page.doc`.
  it("shadows a child field of the same name", () => {
    const { host, controller } = makePage();
    host.doc.value.products[0].trigger = "manual";
    expect(typeof controller.page.rows("products")[0].trigger).toBe("function");
    expect(host.doc.value.products[0].trigger).toBe("manual");
  });
});

describe("fireEvent carries the row (ticket 45 §3)", () => {
  it("hands a dotted key its row and a bare key nothing", async () => {
    const seen: Record<string, any> = {};
    registerRecordPage("CRM Deal", {
      "products.qty": (_page: RecordPageApi, row: PageRow) => (seen.qty = row.rate),
      status: (_page: RecordPageApi, row: PageRow) => (seen.status = row),
    });
    const { controller } = makePage();
    await controller.fireEvent("products.qty", {
      parentfield: "products",
      key: "name:row-b",
    });
    await controller.fireEvent("status");
    expect(seen.qty).toBe(10);
    expect(seen.status).toBeUndefined();
  });

  it("hands every source the same live row", async () => {
    const seen: any[] = [];
    registerRecordPage("CRM Deal", {
      "products.qty": (_page: RecordPageApi, row: PageRow) => {
        row.amount = 1;
        seen.push(row.qty);
      },
    });
    const { host, controller } = makePage();
    await controller.fireEvent("products.qty", {
      parentfield: "products",
      key: "name:row-a",
    });
    expect(seen).toEqual([2]);
    expect(host.doc.value.products[0].amount).toBe(1);
  });
});
