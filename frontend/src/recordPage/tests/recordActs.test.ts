// The `record` act surface: it fills the form through the commit channel typing uses, never saves,
// and refuses a bad field before it writes any.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";

vi.mock("frappe-ui", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  frappeRequest: vi.fn(),
}));
vi.mock("@framework/ui/api", () => ({
  runMethod: vi.fn(async () => ({ data: null })),
  getMeta: vi.fn(async () => ({ data: null, children: [] })),
}));

import { ActInvalid, acts } from "@/acts/dispatcher";
import { withRegisteringSource } from "@/pageEngine/context";
import { createRecordPage, type RecordPageHost } from "../createRecordPage";
import { registerRecordPage, resetRegistry } from "../registry";
import type { AuthoredHandlers } from "../types";

const CHILD_FIELDS = [
  { fieldname: "item", fieldtype: "Data" },
  { fieldname: "qty", fieldtype: "Int", default: "1" },
  { fieldname: "note", fieldtype: "Data", depends_on: "eval:doc.qty > 1" },
  { fieldname: "total", fieldtype: "Currency", read_only: 1 as const },
];

const META = {
  name: "CRM Deal",
  fields: [
    { fieldname: "status", fieldtype: "Select", options: "Open\nWon" },
    { fieldname: "notes", fieldtype: "Data", depends_on: "eval:doc.status == 'Won'" },
    { fieldname: "approved", fieldtype: "Check" },
    { fieldname: "total", fieldtype: "Currency", read_only: 1 as const },
    { fieldname: "products", fieldtype: "Table", options: "Deal Product" },
  ],
};

const controllers: ReturnType<typeof createRecordPage>[] = [];

function makePage(doc: Record<string, any> = {}, overrides: Partial<RecordPageHost> = {}) {
  const host: RecordPageHost = {
    app: "frappe",
    doctype: "CRM Deal",
    docname: "CRM-DEAL-1",
    doc: ref({ status: "Open", approved: 0, products: [], ...doc }),
    saved: ref({}),
    meta: ref(META),
    perms: () => ({ read: 1, write: 1 }),
    isDirty: () => false,
    activeTab: () => "details",
    activateTab: () => {},
    save: vi.fn(async () => {}),
    reload: async () => {},
    router: {} as any,
    activityRows: () => [],
    scrollToActivity: async () => true,
    reloadActivity: async () => {},
    fileRows: () => [],
    reloadFiles: async () => {},
    childFields: () => CHILD_FIELDS,
    ...overrides,
  };
  const controller = createRecordPage(host);
  controllers.push(controller);
  return { host, controller, page: controller.page };
}

function register(handlers: AuthoredHandlers) {
  return withRegisteringSource("crm", async () => registerRecordPage("CRM Deal", handlers));
}

async function invalid(promise: Promise<unknown>) {
  const error = (await promise.catch((rejected) => rejected)) as ActInvalid;
  expect(error).toBeInstanceOf(ActInvalid);
  return error.message;
}

beforeEach(() => {
  resetRegistry();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  for (const controller of controllers.splice(0)) controller.leave();
  vi.restoreAllMocks();
});

describe("record.set_values", () => {
  it("commits each value in order, fires its handler and never saves", async () => {
    const order: string[] = [];
    await register({
      status: (page) => void order.push(`status=${page.doc.status}`),
      approved: (page) => void order.push(`approved=${page.doc.approved}`),
    });
    const { controller, page, host } = makePage();
    await controller.refresh();

    const result = await page.run("record.set_values", { values: { status: "Won", approved: true } });

    expect(order).toEqual(["status=Won", "approved=1"]);
    expect(result).toEqual({ values: { status: "Won", approved: 1 }, errors: {} });
    expect(host.save).not.toHaveBeenCalled();
  });

  it("returns a field a handler changed, and a mark a handler set", async () => {
    await register({
      status: (page) => {
        page.doc.total = 99;
        page.fields.setError("notes", "Say why");
      },
    });
    const { controller, page } = makePage();
    await controller.refresh();

    const result = await page.run("record.set_values", { values: { status: "Won" } });

    expect(result).toEqual({ values: { status: "Won", total: 99 }, errors: { notes: "Say why" } });
  });

  it("refuses an unknown, hidden, read-only or table field and writes nothing", async () => {
    const { controller, page, host } = makePage();
    await controller.refresh();
    const set = (values: Record<string, unknown>) => page.run("record.set_values", { values });

    expect(await invalid(set({ status: "Won", nothing: 1 }))).toBe("record.set_values: nothing is not a field of this form");
    expect(await invalid(set({ notes: "x" }))).toBe("record.set_values: notes is hidden now");
    expect(await invalid(set({ total: 5 }))).toBe("record.set_values: total is read-only");
    expect(await invalid(set({ products: [] }))).toContain("products is a table");
    expect(host.doc.value.status).toBe("Open");
  });

  it("clears a mark on a field it sets", async () => {
    const { controller, page } = makePage();
    await controller.refresh();
    page.fields.setError("status", "Pick one");
    await controller.refresh();

    const result = await page.run("record.set_values", { values: { status: "Won" } });

    expect(result).toEqual({ values: { status: "Won" }, errors: {} });
  });

  it("is listed with its text and checked against its input", async () => {
    const { controller, page } = makePage();
    await controller.refresh();

    const listed = (await acts.described()).filter((act) => act.name.startsWith("record."));

    expect(listed.map((act) => [act.name, act.palette, Boolean(act.description), Boolean(act.input)])).toEqual([
      ["record.set_values", false, true, true],
      ["record.add_child_row", false, true, true],
      ["record.set_child_values", false, true, true],
      ["record.remove_child_row", false, true, true],
    ]);
    expect(await invalid(page.run("record.set_values", { status: "Won" }))).toContain("values is required");
  });
});

describe("child row acts", () => {
  it("adds a row with the child defaults, fires onAdd and sets its values", async () => {
    const added = vi.fn();
    await register({ products: { onAdd: (_page, row) => added((row as any)?.qty) } });
    const { controller, page, host } = makePage({ products: [{ name: "r1", item: "A", qty: 2 }] });
    await controller.refresh();

    const result = await page.run("record.add_child_row", { table: "products", values: { item: "B" } });

    expect(result).toMatchObject({ idx: 2, values: { item: "B", qty: 1 }, errors: {} });
    expect(added).toHaveBeenCalledWith(1);
    expect(host.doc.value.products).toHaveLength(2);
  });

  it("refuses a bad cell before it adds a row", async () => {
    const { controller, page, host } = makePage();
    await controller.refresh();

    expect(await invalid(page.run("record.add_child_row", { table: "products", values: { total: 1 } }))).toContain("total is read-only");
    expect(await invalid(page.run("record.add_child_row", { table: "products", values: { note: "x" } }))).toContain("note is hidden now");
    expect(await invalid(page.run("record.add_child_row", { table: "status" }))).toContain("status is not a table");
    expect(host.doc.value.products).toHaveLength(0);
  });

  it("sets cells of a row by its number, and reads a row's depends_on from that row", async () => {
    const fired = vi.fn();
    await register({ products: { qty: (_page, row) => fired((row as any)?.qty) } });
    const { controller, page, host } = makePage({
      products: [
        { name: "r1", item: "A", qty: 1 },
        { name: "r2", item: "B", qty: 5 },
      ],
    });
    await controller.refresh();

    expect(await invalid(page.run("record.set_child_values", { table: "products", idx: 1, values: { note: "x" } }))).toContain("note is hidden now");
    const result = await page.run("record.set_child_values", { table: "products", idx: 2, values: { note: "x", qty: 7 } });

    expect(result).toEqual({ values: { note: "x", qty: 7 }, errors: {} });
    expect(fired).toHaveBeenCalledWith(7);
    expect(host.doc.value.products[1]).toMatchObject({ note: "x", qty: 7 });
  });

  it("names a row's idx range when it is out of range", async () => {
    const { controller, page } = makePage({ products: [{ name: "r1", qty: 1 }] });
    await controller.refresh();

    const message = await invalid(page.run("record.set_child_values", { table: "products", idx: 3, values: { qty: 2 } }));

    expect(message).toBe("record.set_child_values: products has 1 rows; idx must be 1 to 1");
  });

  it("removes a row, fires onRemove and reports the rows left", async () => {
    const removed = vi.fn();
    await register({ products: { onRemove: () => removed() } });
    const { controller, page, host } = makePage({
      products: [
        { name: "r1", item: "A" },
        { name: "r2", item: "B" },
      ],
    });
    await controller.refresh();

    const result = await page.run("record.remove_child_row", { table: "products", idx: 1 });

    expect(result).toEqual({ rows: 1 });
    expect(removed).toHaveBeenCalledOnce();
    expect(host.doc.value.products.map((row: any) => row.item)).toEqual(["B"]);
  });

  it("keys a cell's error by table, row number and fieldname", async () => {
    await register({ products: { qty: (page, row) => void (row as any)?.setError("qty", "Too many") } });
    const { controller, page } = makePage({ products: [{ name: "r1", qty: 1 }] });
    await controller.refresh();

    const result = await page.run("record.set_child_values", { table: "products", idx: 1, values: { qty: 9 } });

    expect(result).toEqual({ values: { qty: 9 }, errors: { "products.1.qty": "Too many" } });
  });
});
