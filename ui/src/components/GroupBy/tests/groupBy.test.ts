import { describe, expect, it } from "vitest";
import {
  aggregateKey,
  columnWidthKey,
  findGroupByField,
  getAggregateFields,
  getGroupByFields,
  isCompleteAggregate,
  parseGroupBy,
  serializeGroupBy,
} from "../groupBy";
import type { RawMetaField } from "../../FormLayout/types";

const FIELDS: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", label: "Status" },
  {
    fieldname: "deal_owner",
    fieldtype: "Link",
    label: "Deal Owner",
    options: "User",
  },
  { fieldname: "deal_value", fieldtype: "Currency", label: "Deal Value" },
  { fieldname: "probability", fieldtype: "Percent", label: "Probability" },
  { fieldname: "close_date", fieldtype: "Date", label: "Close Date" },
  { fieldname: "notes", fieldtype: "Text Editor", label: "Notes" },
  { fieldname: "secret", fieldtype: "Data", label: "Secret", hidden: 1 },
  { fieldname: "column_break", fieldtype: "Column Break" },
];

const names = (fields: { fieldname: string }[]) =>
  fields.map((f) => f.fieldname);

describe("getGroupByFields", () => {
  it("offers visible, labelled fields of a groupable fieldtype, then the user fields", () => {
    expect(names(getGroupByFields(FIELDS))).toEqual([
      "status",
      "deal_owner",
      "close_date",
      "owner",
      "modified_by",
    ]);
  });
});

describe("getAggregateFields", () => {
  it("offers no field to count", () => {
    expect(getAggregateFields(FIELDS, "count")).toEqual([]);
  });

  it("offers only numbers to sum and average", () => {
    expect(names(getAggregateFields(FIELDS, "sum"))).toEqual([
      "deal_value",
      "probability",
    ]);
    expect(names(getAggregateFields(FIELDS, "avg"))).toEqual([
      "deal_value",
      "probability",
    ]);
  });

  it("also offers dates to min and max", () => {
    expect(names(getAggregateFields(FIELDS, "max"))).toEqual([
      "deal_value",
      "probability",
      "close_date",
    ]);
  });
});

describe("findGroupByField", () => {
  it("finds a Meta field, or a standard user field", () => {
    expect(findGroupByField(FIELDS, "status")?.label).toBe("Status");
    expect(findGroupByField(FIELDS, "owner")?.label).toBe("Created By");
    expect(findGroupByField(FIELDS, "missing")).toBeUndefined();
  });
});

describe("isCompleteAggregate", () => {
  it("needs a field for everything but count", () => {
    expect(isCompleteAggregate({ function: "count" })).toBe(true);
    expect(isCompleteAggregate({ function: "sum" })).toBe(false);
    expect(
      isCompleteAggregate({ function: "sum", fieldname: "deal_value" })
    ).toBe(true);
  });
});

describe("serializeGroupBy", () => {
  it("builds the grouped get_list arguments", () => {
    expect(
      serializeGroupBy({
        fields: ["status", "deal_owner"],
        aggregates: [
          { function: "count" },
          { function: "sum", fieldname: "deal_value" },
        ],
      })
    ).toEqual({
      fields: [
        "status",
        "deal_owner",
        { COUNT: "name", as: "_aggregate_0" },
        { SUM: "deal_value", as: "_aggregate_1" },
      ],
      group_by: "status, deal_owner",
      order_by: "_aggregate_0 desc",
    });
  });

  it("skips an aggregate that has no field yet, keeping the keys contiguous", () => {
    const { fields } = serializeGroupBy({
      fields: ["status"],
      aggregates: [
        { function: "avg" },
        { function: "max", fieldname: "close_date" },
      ],
    });
    expect(fields).toEqual([
      "status",
      { MAX: "close_date", as: aggregateKey(0) },
    ]);
  });

  it("leaves the order alone when there is nothing to aggregate", () => {
    expect(
      serializeGroupBy({ fields: ["status"], aggregates: [] }).order_by
    ).toBeUndefined();
  });
});

describe("parseGroupBy", () => {
  const stored = {
    fields: ["status"],
    aggregates: [{ function: "sum", fieldname: "deal_value" }],
  };

  it("reads a grouping from JSON text or an object", () => {
    expect(parseGroupBy(JSON.stringify(stored))).toEqual(stored);
    expect(parseGroupBy(stored)).toEqual(stored);
  });

  it("reads nothing, bad JSON or a grouping without fields as ungrouped", () => {
    expect(parseGroupBy(null)).toBeNull();
    expect(parseGroupBy("")).toBeNull();
    expect(parseGroupBy("{not json")).toBeNull();
    expect(parseGroupBy({ fields: [], aggregates: [] })).toBeNull();
  });

  it("drops malformed fields and aggregates", () => {
    expect(
      parseGroupBy({
        fields: ["status", "", 3],
        aggregates: [
          { function: "count" },
          { function: "median", fieldname: "deal_value" },
          { function: "sum" },
          "count",
        ],
      })
    ).toEqual({ fields: ["status"], aggregates: [{ function: "count" }] });
  });
});

describe("columnWidthKey", () => {
  it("keys a grouped field by name and an aggregate by function and field", () => {
    expect(columnWidthKey("status")).toBe("status");
    expect(columnWidthKey({ function: "count" })).toBe("count:");
    expect(columnWidthKey({ function: "sum", fieldname: "deal_value" })).toBe(
      "sum:deal_value"
    );
  });
});

describe("parseGroupBy widths", () => {
  it("keeps dragged widths and drops anything that isn't one", () => {
    expect(
      parseGroupBy({
        fields: ["status"],
        aggregates: [],
        widths: { status: "240px", "count:": 5, bad: null },
      })
    ).toEqual({
      fields: ["status"],
      aggregates: [],
      widths: { status: "240px" },
    });
  });

  it("leaves widths out when none survive", () => {
    expect(
      parseGroupBy({ fields: ["status"], aggregates: [], widths: ["240px"] })
    ).toEqual({ fields: ["status"], aggregates: [] });
  });
});
