// The marks a save leaves on the form as executable claims: the mandatory check, the
// server's named fields, a script's `setError`, and when each clears.
import { beforeEach, describe, expect, it, vi } from "vitest";
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
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null })),
}));

import { fieldsToLayout } from "@framework/ui/FormLayout";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { createRecordPage, SAVE_VETO, type RecordPageHost } from "../createRecordPage";
import { resetFieldWarnings } from "../fields";
import { registerRecordPage, resetRegistry } from "../registry";
import { resetRowWarnings } from "../rows";

const FIELDS: RawMetaField[] = [
  { fieldname: "customer", fieldtype: "Data", label: "Customer" },
  { fieldname: "qty", fieldtype: "Int", label: "Qty" },
  { fieldname: "items", fieldtype: "Table", label: "Items", options: "Deal Item" },
];

const CHILD: RawMetaField[] = [{ fieldname: "item", fieldtype: "Data", label: "Item" }];

const LAYOUT = fieldsToLayout([
  { fieldname: "customer", fieldtype: "Data", label: "Customer", reqd: true },
  { fieldname: "qty", fieldtype: "Int", label: "Qty" },
  {
    fieldname: "items",
    fieldtype: "Table",
    label: "Items",
    options: "Deal Item",
    childLayout: fieldsToLayout([{ fieldname: "item", fieldtype: "Data", label: "Item", reqd: true }]),
  },
]);

const ITEM = (key: string) => JSON.stringify(["items", key, "item"]);

function makeHost(overrides: Partial<RecordPageHost> = {}) {
  const landed: string[] = [];
  const writes: Record<string, any>[] = [];
  const doc = ref<Record<string, any>>({
    customer: "Acme",
    qty: 1,
    items: [
      { name: "r1", item: "Bolt" },
      { name: "r2", item: "Nut" },
    ],
  });
  const host: RecordPageHost = {
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc,
    saved: ref({}),
    meta: ref({ fields: FIELDS }),
    perms: () => ({}),
    isDirty: () => true,
    activeTab: () => "",
    activateTab: () => {},
    formLayout: () => LAYOUT,
    focusField: (fieldname) => void landed.push(fieldname),
    childFields: () => CHILD,
    save: async () => void writes.push({ ...doc.value }),
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    ...overrides,
  };
  return { host, doc, landed, writes };
}

let warnings: string[];

beforeEach(() => {
  resetRegistry();
  resetFieldWarnings();
  resetRowWarnings();
  warnings = [];
  vi.spyOn(console, "warn").mockImplementation((message: string) => warnings.push(message));
});

describe("the mandatory check", () => {
  it("marks an empty mandatory field, focuses it, and sends nothing", async () => {
    const { host, doc, landed, writes } = makeHost();
    doc.value.customer = "";
    const controller = createRecordPage(host);

    const refused = controller.page.save();

    await expect(refused).rejects.toThrow("Please fill in Customer");
    await expect(refused).rejects.toMatchObject({ name: SAVE_VETO });
    expect(writes).toEqual([]);
    expect(controller.fieldErrors.drawn.value).toEqual({ customer: "Customer is required" });
    expect(landed).toEqual(["customer"]);
  });

  it("marks a child row's empty cell and focuses its table", async () => {
    const { host, doc, landed } = makeHost();
    doc.value.items[1].item = "";
    const controller = createRecordPage(host);

    await expect(controller.page.save()).rejects.toThrow("Please fill in Items");

    expect(controller.fieldErrors.drawn.value).toEqual({ [ITEM("name:r2")]: "Item is required" });
    expect(landed).toEqual(["items"]);
  });

  it("runs after beforeSave, so a handler can still fill the field", async () => {
    const { host, doc, writes } = makeHost();
    doc.value.customer = "";
    registerRecordPage("CRM Deal", {
      beforeSave: (page) => void (page.doc.customer = "Filled"),
    });
    const controller = createRecordPage(host);

    await controller.page.save();

    expect(writes).toEqual([expect.objectContaining({ customer: "Filled" })]);
    expect(controller.fieldErrors.drawn.value).toEqual({});
  });
});

describe("a refused save", () => {
  it("marks the fields the server names, a row by its name, or by its position when it has none", async () => {
    const { host, doc, landed } = makeHost();
    const controller = createRecordPage({
      ...host,
      save: async () => {
        controller.fieldErrors.markRefused(
          [
            { fieldname: "item", parentfield: "items", row: "r2", idx: 1, message: "Nut is gone" },
            { fieldname: "item", parentfield: "items", idx: 1, message: "Bolt is gone" },
            { fieldname: "item", parentfield: "items", row: "r9", idx: 2, message: "Removed row" },
            { fieldname: "qty", message: "Qty is too big" },
          ],
          doc.value,
        );
        throw new Error("Refused");
      },
    });

    await expect(controller.page.save()).rejects.toThrow("Refused");

    expect(controller.fieldErrors.drawn.value).toEqual({
      [ITEM("name:r2")]: "Nut is gone",
      [ITEM("name:r1")]: "Bolt is gone",
      qty: "Qty is too big",
    });
    expect(landed).toEqual(["qty"]);
  });

  it("marks a new row by its position when the server named it before refusing", async () => {
    const { host, doc } = makeHost();
    doc.value.items.push({ __row_id: "row-9", item: "" });
    const controller = createRecordPage({
      ...host,
      save: async () => {
        controller.fieldErrors.markRefused(
          [{ fieldname: "item", parentfield: "items", row: "server-made", idx: 3, message: "Item is required" }],
          doc.value,
        );
        throw new Error("Refused");
      },
    });

    await expect(controller.page.save()).rejects.toThrow();

    expect(controller.fieldErrors.drawn.value).toEqual({ [ITEM("new:row-9")]: "Item is required" });
  });

  it("clears every mark when the next save starts", async () => {
    const { host } = makeHost();
    let drawnAtWrite: unknown;
    const controller = createRecordPage({
      ...host,
      save: async () => void (drawnAtWrite = controller.fieldErrors.drawn.value),
    });
    controller.page.fields.setError("qty", "Qty is too big");

    await controller.page.save();

    expect(drawnAtWrite).toEqual({});
  });
});

describe("page.fields.setError and clearError", () => {
  it("marks a field and clears it", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);

    controller.page.fields.setError("qty", "Quantity must be positive");
    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Quantity must be positive" });

    controller.page.fields.clearError("qty");
    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("returns an Error a beforeSave can throw as a veto, which focuses the field", async () => {
    const { host, landed, writes } = makeHost();
    registerRecordPage("CRM Deal", {
      beforeSave(page) {
        throw page.fields.setError("qty", "Quantity must be positive");
      },
    });
    const controller = createRecordPage(host);

    const refused = controller.page.save();

    await expect(refused).rejects.toThrow("Quantity must be positive");
    await expect(refused).rejects.toMatchObject({ name: SAVE_VETO });
    expect(writes).toEqual([]);
    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Quantity must be positive" });
    expect(landed).toEqual(["qty"]);
  });

  it("lands a field handler's mark when its hold commits", async () => {
    const { host } = makeHost();
    let drawnInHandler: unknown;
    const controller = createRecordPage(host);
    registerRecordPage("CRM Deal", {
      qty(page) {
        page.fields.setError("qty", "Quantity must be positive");
        drawnInHandler = controller.fieldErrors.drawn.value;
      },
    });

    await controller.commits.commit("qty", -1);

    expect(drawnInHandler).toEqual({});
    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Quantity must be positive" });
  });

  it("keeps a field handler's mark when the control sends the committed value again", async () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    registerRecordPage("CRM Deal", {
      qty(page) {
        page.fields.setError("qty", "Quantity must be positive");
      },
    });

    const committed = controller.commits.commit("qty", -1);
    controller.commits.pending("qty", -1);
    await committed;

    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Quantity must be positive" });
    controller.commits.pending("qty", 5);
    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("warns about a field the doctype does not have", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);

    controller.page.fields.setError("qtyy", "Bad");

    expect(warnings).toEqual(['[record-page] page.fields.setError("qtyy") — no such field.']);
  });
});

describe("a row's setError and clearError", () => {
  it("marks one cell of its row and clears it", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    const [, second] = controller.page.rows("items");

    second.setError("item", "Nut is out of stock");
    expect(controller.fieldErrors.drawn.value).toEqual({ [ITEM("name:r2")]: "Nut is out of stock" });

    second.clearError("item");
    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("warns about a field the child doctype does not have", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);

    controller.page.rows("items")[0].setError("itme", "Bad");

    expect(warnings).toEqual([
      '[record-page] row.setError("itme") on items — no such field on the child doctype.',
    ]);
  });
});

describe("when a mark clears", () => {
  it("clears on the field's live edit, and a cell's on the cell's", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    controller.page.fields.setError("qty", "Bad qty");
    controller.page.rows("items")[0].setError("item", "Bad item");

    controller.commits.pending("qty", 2);
    controller.commits.pending("item", "Washer", { parentfield: "items", key: "name:r1" });

    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("clears a table's mark when a row is added", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    controller.page.fields.setError("items", "Items is required");

    controller.commits.rowChanged({ parentfield: "items", key: "new:row-1" }, "add");

    expect(controller.fieldErrors.drawn.value).toEqual({});
  });

  it("clears a removed row's cells, and leaves the other rows'", () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    const [first, second] = controller.page.rows("items");
    first.setError("item", "Bad bolt");
    second.setError("item", "Bad nut");

    controller.commits.rowChanged({ parentfield: "items", key: "name:r1" }, "remove");

    expect(controller.fieldErrors.drawn.value).toEqual({ [ITEM("name:r2")]: "Bad nut" });
  });

  it("clears on a replay, which keeps what its own onRefresh marks", async () => {
    const { host } = makeHost();
    const controller = createRecordPage(host);
    controller.page.fields.setError("customer", "Stale");
    registerRecordPage("CRM Deal", {
      onRefresh: (page) => void page.fields.setError("qty", "Quantity must be positive"),
    });

    await controller.refresh();

    expect(controller.fieldErrors.drawn.value).toEqual({ qty: "Quantity must be positive" });
  });
});
