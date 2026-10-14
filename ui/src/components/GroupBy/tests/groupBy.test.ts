import { describe, expect, it } from "vitest";
import {
  columnId,
  effectiveSort,
  findGroupByField,
  getAggregateFields,
  getGroupByFields,
  isAggregateTaken,
  isCompleteAggregate,
  parseGroupBy,
  serializeGroupBy,
  serializeGroupByTotals,
} from "../groupBy";
import type { RawMetaField } from "../../FormLayout/types";
import type { AggregateDraft } from "../types";

const FIELDS: RawMetaField[] = [
  { fieldname: "status", fieldtype: "Select", label: "Status" },
  {
    fieldname: "sales_person",
    fieldtype: "Link",
    label: "Sales Person",
    options: "User",
  },
  { fieldname: "grand_total", fieldtype: "Currency", label: "Grand Total" },
  { fieldname: "probability", fieldtype: "Percent", label: "Probability" },
  { fieldname: "close_date", fieldtype: "Date", label: "Close Date" },
  { fieldname: "notes", fieldtype: "Text Editor", label: "Notes" },
  { fieldname: "secret", fieldtype: "Data", label: "Secret", hidden: 1 },
  { fieldname: "column_break", fieldtype: "Column Break" },
];

const names = (fields: { fieldname: string }[]) =>
  fields.map((f) => f.fieldname);

describe("getGroupByFields", () => {
  it("offers labelled fields of a groupable fieldtype, hidden ones too, then the standard fields", () => {
    expect(names(getGroupByFields(FIELDS))).toEqual([
      "status",
      "sales_person",
      "close_date",
      "secret",
      "owner",
      "modified_by",
      "_user_tags",
      "docstatus",
    ]);
  });

  it("leaves out virtual fields, which have no column to group on", () => {
    expect(
      names(
        getGroupByFields([
          { fieldname: "region", fieldtype: "Data", label: "Region" },
          {
            fieldname: "age",
            fieldtype: "Int",
            label: "Age",
            is_virtual: 1,
          },
        ])
      )
    ).toEqual(["region", "owner", "modified_by", "_user_tags", "docstatus"]);
  });
});

describe("getAggregateFields", () => {
  it("offers no field to count", () => {
    expect(getAggregateFields(FIELDS, "count")).toEqual([]);
  });

  it("offers only numbers to sum and average", () => {
    expect(names(getAggregateFields(FIELDS, "sum"))).toEqual([
      "grand_total",
      "probability",
    ]);
    expect(names(getAggregateFields(FIELDS, "avg"))).toEqual([
      "grand_total",
      "probability",
    ]);
  });

  it("offers hidden numbers, but not virtual ones or ratings", () => {
    expect(
      names(
        getAggregateFields(
          [
            {
              fieldname: "cost",
              fieldtype: "Currency",
              label: "Cost",
              hidden: 1,
            },
            {
              fieldname: "margin",
              fieldtype: "Float",
              label: "Margin",
              is_virtual: 1,
            },
            { fieldname: "stars", fieldtype: "Rating", label: "Stars" },
          ],
          "sum"
        )
      )
    ).toEqual(["cost"]);
  });

  it("also offers dates and the standard timestamps to min and max", () => {
    expect(names(getAggregateFields(FIELDS, "max"))).toEqual([
      "grand_total",
      "probability",
      "close_date",
      "creation",
      "modified",
    ]);
  });
});

describe("findGroupByField", () => {
  it("finds a Meta field, or a standard field", () => {
    expect(findGroupByField(FIELDS, "status")?.label).toBe("Status");
    expect(findGroupByField(FIELDS, "owner")?.label).toBe("Created By");
    expect(findGroupByField(FIELDS, "docstatus")?.label).toBe(
      "Document Status"
    );
    expect(findGroupByField(FIELDS, "missing")).toBeUndefined();
  });
});

describe("isCompleteAggregate", () => {
  it("needs a field for everything but count", () => {
    expect(isCompleteAggregate({ function: "count" })).toBe(true);
    expect(isCompleteAggregate({ function: "sum" })).toBe(false);
    expect(
      isCompleteAggregate({ function: "sum", fieldname: "grand_total" })
    ).toBe(true);
  });
});

describe("isAggregateTaken", () => {
  const aggregates: AggregateDraft[] = [
    { function: "count" },
    { function: "sum", fieldname: "grand_total" },
    { function: "avg" },
  ];

  it("takes a second count", () => {
    expect(isAggregateTaken(aggregates, 2, { function: "count" })).toBe(true);
  });

  it("takes the same function on the same field", () => {
    expect(
      isAggregateTaken(aggregates, 2, {
        function: "sum",
        fieldname: "grand_total",
      })
    ).toBe(true);
  });

  it("allows the same field under another function", () => {
    expect(
      isAggregateTaken(aggregates, 2, {
        function: "avg",
        fieldname: "grand_total",
      })
    ).toBe(false);
  });

  it("never takes a row with no field yet", () => {
    expect(isAggregateTaken(aggregates, 1, { function: "avg" })).toBe(false);
    expect(isAggregateTaken(aggregates, 2, { function: "sum" })).toBe(false);
  });

  it("ignores the row's own index", () => {
    expect(isAggregateTaken(aggregates, 0, { function: "count" })).toBe(false);
    expect(
      isAggregateTaken(aggregates, 1, {
        function: "sum",
        fieldname: "grand_total",
      })
    ).toBe(false);
  });
});

describe("serializeGroupBy", () => {
  it("builds the grouped get_list arguments", () => {
    expect(
      serializeGroupBy({
        fields: ["status", "sales_person"],
        aggregates: [
          { function: "count" },
          { function: "sum", fieldname: "grand_total" },
        ],
      })
    ).toEqual({
      fields: [
        "status",
        "sales_person",
        { COUNT: "name", as: "_aggregate_0" },
        { SUM: "grand_total", as: "_aggregate_1" },
      ],
      group_by: "status, sales_person",
      order_by: "_aggregate_0 desc, status asc, sales_person asc",
    });
  });

  it("orders by the group fields when there is nothing to aggregate", () => {
    expect(
      serializeGroupBy({ fields: ["status", "sales_person"], aggregates: [] })
        .order_by
    ).toBe("status asc, sales_person asc");
  });
});

describe("parseGroupBy", () => {
  const stored = {
    fields: ["status"],
    aggregates: [{ function: "sum", fieldname: "grand_total" }],
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
          { function: "median", fieldname: "grand_total" },
          { function: "sum" },
          "count",
        ],
      })
    ).toEqual({ fields: ["status"], aggregates: [{ function: "count" }] });
  });

  it("keeps one of an aggregate saved twice", () => {
    expect(
      parseGroupBy({
        fields: ["status"],
        aggregates: [
          { function: "count" },
          { function: "sum", fieldname: "grand_total" },
          { function: "count" },
          { function: "avg", fieldname: "grand_total" },
          { function: "sum", fieldname: "grand_total" },
        ],
      })
    ).toEqual({
      fields: ["status"],
      aggregates: [
        { function: "count" },
        { function: "sum", fieldname: "grand_total" },
        { function: "avg", fieldname: "grand_total" },
      ],
    });
  });
});

describe("columnId", () => {
  it("keys a grouped field by name and an aggregate by function and field", () => {
    expect(columnId("status")).toBe("status");
    expect(columnId({ function: "count" })).toBe("count:");
    expect(columnId({ function: "sum", fieldname: "grand_total" })).toBe(
      "sum:grand_total"
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

describe("serializeGroupBy sort", () => {
  const groupBy = {
    fields: ["status"],
    aggregates: [
      { function: "count" as const },
      { function: "sum" as const, fieldname: "grand_total" },
    ],
  };

  it("orders by a grouped field, then the other group fields", () => {
    expect(
      serializeGroupBy({
        ...groupBy,
        fields: ["status", "sales_person"],
        sort: [{ fieldname: "sales_person", direction: "desc" }],
      }).order_by
    ).toBe("sales_person desc, status asc");
  });

  it("orders by an aggregate through its column id", () => {
    expect(
      serializeGroupBy({
        ...groupBy,
        sort: [{ fieldname: "sum:grand_total", direction: "asc" }],
      }).order_by
    ).toBe("_aggregate_1 asc, status asc");
  });

  it("falls back to the first aggregate when the sorted column is gone", () => {
    expect(
      serializeGroupBy({
        ...groupBy,
        sort: [{ fieldname: "avg:probability", direction: "asc" }],
      }).order_by
    ).toBe("_aggregate_0 desc, status asc");
  });
});

describe("effectiveSort", () => {
  const groupBy = {
    fields: ["status"],
    aggregates: [
      { function: "count" as const },
      { function: "sum" as const, fieldname: "grand_total" },
    ],
  };

  it("keeps the chosen sort while its column is shown", () => {
    const sort = [{ fieldname: "sum:grand_total", direction: "asc" as const }];
    expect(effectiveSort({ ...groupBy, sort })).toEqual(sort);
  });

  it("falls back to the first aggregate, largest first, then to nothing", () => {
    const sort = [{ fieldname: "region", direction: "asc" as const }];
    expect(effectiveSort({ ...groupBy, sort })).toEqual([
      { fieldname: "count:", direction: "desc" },
    ]);
    expect(effectiveSort({ fields: ["status"], aggregates: [] })).toEqual([]);
  });
});

describe("serializeGroupByTotals", () => {
  it("runs the aggregates ungrouped", () => {
    expect(
      serializeGroupByTotals({
        fields: ["status"],
        aggregates: [{ function: "avg", fieldname: "grand_total" }],
      })
    ).toEqual({ fields: [{ AVG: "grand_total", as: "_aggregate_0" }] });
  });

  it("has nothing to total without aggregates", () => {
    expect(
      serializeGroupByTotals({ fields: ["status"], aggregates: [] })
    ).toBeNull();
  });
});

describe("getGroupByFields fieldtypes", () => {
  it("offers Dynamic Link and Autocomplete fields, as desk does", () => {
    expect(
      names(
        getGroupByFields([
          { fieldname: "ref", fieldtype: "Dynamic Link", label: "Reference" },
          { fieldname: "city", fieldtype: "Autocomplete", label: "City" },
        ])
      )
    ).toEqual([
      "ref",
      "city",
      "owner",
      "modified_by",
      "_user_tags",
      "docstatus",
    ]);
  });
});

describe("parseGroupBy sort and totals", () => {
  it("keeps a valid sort and the totals flag", () => {
    expect(
      parseGroupBy({
        fields: ["status"],
        aggregates: [],
        sort: [{ fieldname: "status", direction: "asc" }],
        showTotals: true,
      })
    ).toEqual({
      fields: ["status"],
      aggregates: [],
      sort: [{ fieldname: "status", direction: "asc" }],
      showTotals: true,
    });
  });

  it("drops a malformed sort", () => {
    expect(
      parseGroupBy({
        fields: ["status"],
        aggregates: [],
        sort: [{ fieldname: "status", direction: "sideways" }],
        showTotals: "yes",
      })
    ).toEqual({ fields: ["status"], aggregates: [] });
  });
});
