import { describe, expect, it } from "vitest";
import { layoutFields, newRowValues } from "../newRowValues";
import type { FieldNode, FormLayoutSchema } from "../types";

const field = (over: Partial<FieldNode> & { fieldname: string }): FieldNode =>
  ({ fieldtype: "Data", ...over }) as FieldNode;

describe("newRowValues", () => {
  it("seeds declared defaults and leaves the rest absent", () => {
    expect(
      newRowValues([
        field({ fieldname: "item_code" }),
        field({ fieldname: "uom", default: "Nos" }),
      ])
    ).toEqual({ uom: "Nos" });
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
