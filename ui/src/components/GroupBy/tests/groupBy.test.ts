import { describe, expect, it } from "vitest";
import {
  columnId,
  effectiveSort,
  findGroupByField,
  formatRating,
  getAggregateFields,
  getGroupByFields,
  groupsByAssignee,
  isAggregateTaken,
  isCompleteAggregate,
  parseGroupBy,
  serializeGroupBy,
  serializeGroupByTotals,
  splitAssignees,
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
      "_assign",
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
    ).toEqual([
      "region",
      "_assign",
      "owner",
      "modified_by",
      "_user_tags",
      "docstatus",
    ]);
  });

  it("leaves out excluded fields, standard ones included", () => {
    expect(names(getGroupByFields(FIELDS, ["sales_person", "owner"]))).toEqual([
      "status",
      "close_date",
      "secret",
      "_assign",
      "modified_by",
      "_user_tags",
      "docstatus",
    ]);
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

  it("leaves out excluded fields, standard ones included", () => {
    expect(names(getAggregateFields(FIELDS, "sum", ["probability"]))).toEqual([
      "grand_total",
    ]);
    expect(
      names(getAggregateFields(FIELDS, "max", ["close_date", "modified"]))
    ).toEqual(["grand_total", "probability", "creation"]);
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
    expect(findGroupByField(FIELDS, "_assign")).toMatchObject({
      label: "Assigned To",
      options: "User",
    });
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

describe("grouping by assignee", () => {
  const BY_ASSIGNEE = {
    fields: ["_assign"],
    aggregates: [
      { function: "count" as const },
      { function: "avg" as const, fieldname: "grand_total" },
      { function: "max" as const, fieldname: "close_date" },
    ],
  };

  it("is on only while _assign is a group field", () => {
    expect(groupsByAssignee(BY_ASSIGNEE)).toBe(true);
    expect(groupsByAssignee({ fields: ["status"], aggregates: [] })).toBe(
      false
    );
  });

  it("fetches averages as a sum and a count, so split groups can add up", () => {
    expect(serializeGroupBy(BY_ASSIGNEE)).toEqual({
      fields: [
        "_assign",
        { COUNT: "name", as: "_aggregate_0" },
        { SUM: "grand_total", as: "_aggregate_1_sum" },
        { COUNT: "grand_total", as: "_aggregate_1_count" },
        { MAX: "close_date", as: "_aggregate_2" },
      ],
      group_by: "_assign",
      order_by: "_assign asc",
    });
  });

  it("counts a record under each of its assignees, and unassigned ones once", () => {
    const rows = [
      {
        _assign: '["ann@x.com"]',
        _aggregate_0: 2,
        _aggregate_1_sum: 300,
        _aggregate_1_count: 2,
        _aggregate_2: "2026-01-05",
      },
      {
        _assign: '["ann@x.com", "bob@x.com"]',
        _aggregate_0: 1,
        _aggregate_1_sum: null,
        _aggregate_1_count: 0,
        _aggregate_2: "2026-03-01",
      },
      {
        _assign: null,
        _aggregate_0: 4,
        _aggregate_1_sum: 40,
        _aggregate_1_count: 4,
        _aggregate_2: null,
      },
      {
        _assign: "[]",
        _aggregate_0: 1,
        _aggregate_1_sum: 60,
        _aggregate_1_count: 1,
        _aggregate_2: "2026-02-01",
      },
    ];
    expect(splitAssignees(rows, BY_ASSIGNEE)).toEqual([
      {
        _assign: null,
        _aggregate_0: 5,
        _aggregate_1: 20,
        _aggregate_2: "2026-02-01",
      },
      {
        _assign: "ann@x.com",
        _aggregate_0: 3,
        _aggregate_1: 150,
        _aggregate_2: "2026-03-01",
      },
      {
        _assign: "bob@x.com",
        _aggregate_0: 1,
        _aggregate_1: null,
        _aggregate_2: "2026-03-01",
      },
    ]);
  });

  it("compares unpadded times as times", () => {
    const rows = [
      { _assign: '["ann@x.com"]', _aggregate_0: "10:00:00" },
      { _assign: '["ann@x.com", "bob@x.com"]', _aggregate_0: "9:00:00" },
    ];
    const byMin = splitAssignees(rows, {
      fields: ["_assign"],
      aggregates: [{ function: "min", fieldname: "start_time" }],
    });
    expect(byMin.map((r) => r._aggregate_0)).toEqual(["9:00:00", "9:00:00"]);
    const byMax = splitAssignees(rows, {
      fields: ["_assign"],
      aggregates: [{ function: "max", fieldname: "start_time" }],
    });
    expect(byMax).toEqual([
      { _assign: "ann@x.com", _aggregate_0: "10:00:00" },
      { _assign: "bob@x.com", _aggregate_0: "9:00:00" },
    ]);
  });

  it("sorts time-shaped text in a group field as text", () => {
    const rows = [
      { slot: "10:00", _assign: '["ann@x.com"]' },
      { slot: "9:00", _assign: '["ann@x.com"]' },
    ];
    const split = splitAssignees(rows, {
      fields: ["slot", "_assign"],
      aggregates: [],
    });
    expect(split.map((r) => r.slot)).toEqual(["10:00", "9:00"]);
  });

  it("splits within the other group fields and sorts by the chosen column", () => {
    const rows = [
      {
        status: "Open",
        _assign: '["bob@x.com", "ann@x.com"]',
        _aggregate_0: 1,
      },
      { status: "Open", _assign: '["ann@x.com"]', _aggregate_0: 1 },
      { status: "Closed", _assign: '["ann@x.com"]', _aggregate_0: 5 },
    ];
    const split = splitAssignees(rows, {
      fields: ["status", "_assign"],
      aggregates: [{ function: "count" }],
      sort: [{ fieldname: "_assign", direction: "asc" }],
    });
    expect(split).toEqual([
      { status: "Closed", _assign: "ann@x.com", _aggregate_0: 5 },
      { status: "Open", _assign: "ann@x.com", _aggregate_0: 2 },
      { status: "Open", _assign: "bob@x.com", _aggregate_0: 1 },
    ]);
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
      "_assign",
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

describe("Rating fields", () => {
  const RATED: RawMetaField[] = [
    { fieldname: "rating", fieldtype: "Rating", label: "Rating" },
    { fieldname: "grand_total", fieldtype: "Currency", label: "Grand Total" },
  ];
  const names = (fields: { fieldname: string }[]) =>
    fields.map((f) => f.fieldname);

  it("can be grouped by", () => {
    expect(names(getGroupByFields(RATED))).toContain("rating");
  });

  it("can be averaged and ranged but not summed", () => {
    expect(names(getAggregateFields(RATED, "avg"))).toEqual([
      "rating",
      "grand_total",
    ]);
    expect(names(getAggregateFields(RATED, "max"))).toContain("rating");
    expect(names(getAggregateFields(RATED, "sum"))).toEqual(["grand_total"]);
  });

  it("shows a rating on its star scale", () => {
    expect(formatRating(0.6)).toBe("3 / 5");
    expect(formatRating(0.54)).toBe("2.7 / 5");
    expect(formatRating(0.5, "10")).toBe("5 / 10");
  });
});
