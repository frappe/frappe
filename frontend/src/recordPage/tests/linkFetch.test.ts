import { beforeEach, describe, expect, it, vi } from "vitest";
import { runMethod } from "@framework/ui/api";
import type { RawMetaField } from "@framework/ui/FormLayout/types";
import { FieldErrors } from "../fieldErrors";
import { fetchTargets, LinkFetch } from "../linkFetch";

vi.mock("@framework/ui/api", () => ({ runMethod: vi.fn() }));
const mockedCall = vi.mocked(runMethod);

const FIELDS: RawMetaField[] = [
  {
    fieldname: "customer",
    fieldtype: "Link",
    options: "Customer",
    link_filters: JSON.stringify([["Customer", "company", "=", "eval:doc.company"]]),
  },
  { fieldname: "customer_name", fieldtype: "Data", fetch_from: "customer.customer_name" },
  { fieldname: "tax_id", fieldtype: "Data", fetch_from: "customer.tax_id", fetch_if_empty: 1 },
  { fieldname: "items", fieldtype: "Table", options: "Order Item" },
];
const ROW_FIELDS: RawMetaField[] = [
  { fieldname: "item", fieldtype: "Link", options: "Item" },
  { fieldname: "uom", fieldtype: "Data", fetch_from: "item.stock_uom" },
];

describe("fetchTargets", () => {
  it("fetches a plain fetch_from field even when it holds a value", () => {
    expect(fetchTargets(FIELDS, "customer", { customer_name: "Old" })).toMatchObject({
      customer_name: "customer_name",
    });
  });

  it("fetches a fetch_if_empty field only while it is empty", () => {
    expect(fetchTargets(FIELDS, "customer", { tax_id: "" })).toHaveProperty("tax_id", "tax_id");
    expect(fetchTargets(FIELDS, "customer", { tax_id: "GB1" })).not.toHaveProperty("tax_id");
  });

  it("names only fields fetched from that Link", () => {
    expect(fetchTargets(FIELDS, "supplier", {})).toEqual({});
  });

  it("skips a fieldtype v1 does not fetch into, unless it is read-only", () => {
    const notes = { fieldname: "notes", fieldtype: "Long Text", fetch_from: "customer.notes" };
    expect(fetchTargets([notes], "customer", {})).toEqual({});
    expect(fetchTargets([{ ...notes, read_only: 1 }], "customer", {})).toEqual({ notes: "notes" });
  });
});

describe("LinkFetch", () => {
  let doc: Record<string, any>;
  let errors: FieldErrors;
  let fetcher: LinkFetch;
  let scriptFilters: Record<string, Record<string, unknown>>;

  beforeEach(() => {
    mockedCall.mockReset();
    doc = { company: "Acme", customer: "C-1", customer_name: "Old", tax_id: "GB1", items: [] };
    errors = new FieldErrors();
    scriptFilters = {};
    fetcher = new LinkFetch({
      doc: () => doc,
      fields: () => FIELDS,
      childFields: (doctype) => (doctype === "Order Item" ? ROW_FIELDS : undefined),
      scriptFilters: (name) => scriptFilters[name],
      errors,
    });
  });

  it("checks the value with the resolved filters and copies what it fetched", async () => {
    mockedCall.mockResolvedValue({ data: { name: "C-1", customer_name: "New" } } as never);
    scriptFilters.customer = { disabled: 0, company: ["=", "Script"] };
    expect(await fetcher.run("customer")).toEqual(["customer_name"]);
    expect(mockedCall).toHaveBeenCalledWith("frappe.client.validate_link_and_fetch", {
      doctype: "Customer",
      docname: "C-1",
      fields_to_fetch: ["customer_name"],
      filters: { disabled: 0, company: ["=", "Acme"] },
    });
    expect(doc).toMatchObject({ customer: "C-1", customer_name: "New", tax_id: "GB1" });
  });

  it("clears and marks a value the filters exclude", async () => {
    mockedCall.mockResolvedValue({ data: {} } as never);
    await fetcher.run("customer");
    expect(doc.customer).toBeNull();
    expect(doc.customer_name).toBeNull();
    expect(Object.values(errors.drawn.value)).toEqual(["C-1 does not match this field's filters"]);
  });

  it("empties the fetched fields without a call when the Link is cleared", async () => {
    doc.customer = null;
    await fetcher.run("customer");
    expect(mockedCall).not.toHaveBeenCalled();
    expect(doc.customer_name).toBeNull();
  });

  it("drops an answer the reader has since overtaken", async () => {
    mockedCall.mockImplementation(async () => {
      doc.customer = "C-2";
      return { data: { name: "C-1", customer_name: "New" } } as never;
    });
    await fetcher.run("customer");
    expect(doc.customer_name).toBe("Old");
  });

  it("fetches into a child row", async () => {
    doc.items = [{ name: "r1", item: "I-1", uom: "" }];
    mockedCall.mockResolvedValue({ data: { name: "I-1", stock_uom: "Nos" } } as never);
    await fetcher.run("item", { parentfield: "items", key: "name:r1" });
    expect(doc.items[0].uom).toBe("Nos");
  });

  it("marks a missing record as not found when the field has no filters", async () => {
    doc.items = [{ name: "r1", item: "I-9", uom: "Box" }];
    mockedCall.mockResolvedValue({ data: {} } as never);
    await fetcher.run("item", { parentfield: "items", key: "name:r1" });
    expect(doc.items[0]).toMatchObject({ item: null, uom: null });
    expect(Object.values(errors.drawn.value)).toEqual(["I-9 not found"]);
  });

  it("makes no call for a Link with neither filters nor fetches", async () => {
    await fetcher.run("company");
    doc.items = [{ name: "r1", item: "I-1" }];
    await fetcher.run("uom", { parentfield: "items", key: "name:r1" });
    expect(mockedCall).not.toHaveBeenCalled();
  });
});
