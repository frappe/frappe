import { describe, expect, it } from "vitest";
import { layoutFields, newRowValues } from "../newRowValues";
import type { FieldNode, FormLayoutSchema } from "../types";

const field = (over: Partial<FieldNode> & { fieldname: string }): FieldNode =>
  ({ fieldtype: "Data", ...over }) as FieldNode;

describe("newRowValues", () => {
  it("seeds declared defaults and gives every other field a typed empty", () => {
    expect(
      newRowValues([
        field({ fieldname: "item_code" }),
        field({ fieldname: "uom", default: "Nos" }),
      ])
    ).toEqual({ item_code: "", uom: "Nos" });
  });

  it("empties a numeric field to 0 and a Check to false, so arithmetic works", () => {
    const row = newRowValues([
      field({ fieldname: "qty", fieldtype: "Int" }),
      field({ fieldname: "rate", fieldtype: "Currency" }),
      field({ fieldname: "discount", fieldtype: "Percent" }),
      field({ fieldname: "weight", fieldtype: "Float" }),
      field({ fieldname: "free", fieldtype: "Check" }),
    ]);
    expect(row).toEqual({ qty: 0, rate: 0, discount: 0, weight: 0, free: false });
    expect(row.qty * row.rate).toBe(0);
  });

  it("empties every numeric fieldtype the server can send back", () => {
    // Rating and Duration are `decimal` columns and Long Int a `bigint`, so a
    // loaded row carries numbers for all three (frappe/database/mariadb).
    expect(
      newRowValues([
        field({ fieldname: "score", fieldtype: "Rating" }),
        field({ fieldname: "spent", fieldtype: "Duration" }),
        field({ fieldname: "big", fieldtype: "Long Int" }),
      ])
    ).toEqual({ score: 0, spent: 0, big: 0 });
  });

  it("empties a nested collection to [] and skips the fieldtypes with no value", () => {
    expect(
      newRowValues([
        field({ fieldname: "items", fieldtype: "Table" }),
        field({ fieldname: "tags", fieldtype: "Table MultiSelect" }),
        field({ fieldname: "go", fieldtype: "Button" }),
        field({ fieldname: "pic", fieldtype: "Image" }),
      ])
    ).toEqual({ items: [], tags: [] });
  });

  // Note the date-ish types: the server nulls an empty datetime on write
  // (`get_valid_dict`), so `""` is ticket 56's choice rather than a match for
  // what a loaded row carries.
  it("empties the string-ish types, including the date-ish ones, to \"\"", () => {
    expect(
      newRowValues([
        field({ fieldname: "notes", fieldtype: "Text" }),
        field({ fieldname: "item", fieldtype: "Link" }),
        field({ fieldname: "due", fieldtype: "Date" }),
        field({ fieldname: "at", fieldtype: "Datetime" }),
      ])
    ).toEqual({ notes: "", item: "", due: "", at: "" });
  });

  it("empties a Select with no options rather than dropping it", () => {
    expect(
      newRowValues([field({ fieldname: "status", fieldtype: "Select" })])
    ).toEqual({ status: "" });
  });

  it("coerces numeric defaults to numbers", () => {
    expect(
      newRowValues([
        field({ fieldname: "qty", fieldtype: "Float", default: "1" }),
        field({ fieldname: "free", fieldtype: "Check", default: "1" }),
        field({ fieldname: "rate", fieldtype: "Currency", default: "2.5" }),
      ])
    ).toEqual({ qty: 1, free: 1, rate: 2.5 });
  });

  it("lands a Select on its first option when it declares no default", () => {
    expect(
      newRowValues([
        field({ fieldname: "status", fieldtype: "Select", options: "Open\nClosed" }),
      ])
    ).toEqual({ status: "Open" });
  });

  it("resolves Today to a date", () => {
    const row = newRowValues([
      field({ fieldname: "due", fieldtype: "Date", default: "Today" }),
    ]);
    expect(row.due).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("skips fieldtypes that hold no value", () => {
    expect(
      newRowValues([field({ fieldname: "sb", fieldtype: "Section Break", default: "x" })])
    ).toEqual({});
  });
});

describe("layoutFields", () => {
  it("flattens every field of a child layout, not just the grid columns", () => {
    const layout: FormLayoutSchema = [
      {
        name: "t",
        sections: [
          { name: "s", columns: [{ fields: [field({ fieldname: "qty" })] }] },
          { name: "s2", columns: [{ fields: [field({ fieldname: "notes" })] }] },
        ],
      },
    ];
    expect(layoutFields(layout).map((f) => f.fieldname)).toEqual(["qty", "notes"]);
  });
});
