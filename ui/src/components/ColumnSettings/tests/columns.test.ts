import { describe, expect, it } from "vitest";
import {
  applyColumnWidth,
  clearColumnWidth,
  dropOrphanedSyntheticColumns,
  fetchFields,
  getColumnAlign,
  parseColumns,
  serializeColumns,
} from "../columns";
import type { RawMetaField } from "../../FormLayout/types";
import type { Column, WireColumn } from "../types";

const FIELDS: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    options: "Open\nClosed",
  },
  { fieldname: "amount", fieldtype: "Currency", label: "Amount" },
];

describe("getColumnAlign", () => {
  it("aligns numeric fieldtypes right", () => {
    for (const fieldtype of [
      "Int",
      "Float",
      "Currency",
      "Percent",
      "Duration",
    ]) {
      expect(getColumnAlign(fieldtype)).toBe("right");
    }
  });

  it("aligns every other fieldtype left", () => {
    for (const fieldtype of ["Data", "Link", "Select", "Datetime", "Check"]) {
      expect(getColumnAlign(fieldtype)).toBe("left");
    }
  });
});

describe("serializeColumns", () => {
  it("derives type/options/align from Meta and keys on fieldname", () => {
    const wire = serializeColumns(
      [{ fieldname: "amount", label: "Deal Amount", width: "8rem" }],
      FIELDS
    );
    expect(wire).toEqual([
      {
        key: "amount",
        label: "Deal Amount",
        width: "8rem",
        type: "Currency",
        options: undefined,
        align: "right",
      },
    ]);
  });

  it("flexes a width-less Column to an fr, larger for the leading column", () => {
    const wire = serializeColumns(
      [
        { fieldname: "name", label: "Name" },
        { fieldname: "status", label: "Status" },
      ],
      FIELDS
    );
    expect(wire.map((w) => w.width)).toEqual([2, 1]);
    expect(wire[1].options).toBe("Open\nClosed");
    expect(wire[1].align).toBe("left");
  });

  it("keeps a resized column's fixed px width instead of flexing it", () => {
    const wire = serializeColumns(
      [
        { fieldname: "name", label: "Name", width: "150px" },
        { fieldname: "status", label: "Status" },
      ],
      FIELDS
    );
    expect(wire.map((w) => w.width)).toEqual(["150px", 1]);
  });

  it("falls back to a left-aligned Data column for fields absent from Meta", () => {
    const [wire] = serializeColumns(
      [{ fieldname: "name", label: "ID" }],
      FIELDS
    );
    expect(wire).toEqual({
      key: "name",
      label: "ID",
      width: 2,
      type: "Data",
      options: undefined,
      align: "left",
    });
  });

  it("emits a synthetic column's render metadata from its declaration, not Meta", () => {
    const [, wire] = serializeColumns(
      [
        { fieldname: "name", label: "Name" },
        { fieldname: "_indicator", label: "Status" },
      ],
      FIELDS,
      [
        {
          key: "_indicator",
          label: "Status",
          type: "Status",
          place: "after-title",
        },
      ]
    );
    expect(wire).toEqual({
      key: "_indicator",
      label: "Status",
      width: 1,
      type: "Status",
      options: undefined,
      align: "left",
    });
  });

  it("keeps a resized synthetic column's stored width over the declaration default", () => {
    const [wire] = serializeColumns(
      [{ fieldname: "_indicator", label: "Status", width: "12rem" }],
      FIELDS,
      [{ key: "_indicator", label: "Status", type: "Status", width: "8rem" }]
    );
    expect(wire.width).toBe("12rem");
  });

  it("honors an explicit align on the declaration over the type-derived default", () => {
    const [wire] = serializeColumns(
      [{ fieldname: "_amount", label: "Total" }],
      FIELDS,
      [{ key: "_amount", label: "Total", type: "Data", align: "right" }]
    );
    expect(wire.align).toBe("right");
  });
});

describe("parseColumns", () => {
  it("drops the Meta-derived type/options/align and keys back on fieldname", () => {
    expect(
      parseColumns([
        {
          key: "amount",
          label: "Deal Amount",
          width: "8rem",
          type: "Currency",
          options: undefined,
          align: "right",
        },
      ])
    ).toEqual([{ fieldname: "amount", label: "Deal Amount", width: "8rem" }]);
  });

  it("round-trips a Column[] through serialize → parse", () => {
    const columns: Column[] = [
      { fieldname: "amount", label: "Deal Amount", width: "8rem" },
      { fieldname: "status", label: "Status", width: "10rem" },
    ];
    expect(parseColumns(serializeColumns(columns, FIELDS))).toEqual(columns);
  });
});

describe("applyColumnWidth", () => {
  const columns: Column[] = [
    { fieldname: "amount", label: "Amount", width: "8rem" },
    { fieldname: "status", label: "Status" },
  ];

  it("writes the new width into the matching column by fieldname", () => {
    expect(applyColumnWidth(columns, "status", "120px")).toEqual([
      { fieldname: "amount", label: "Amount", width: "8rem" },
      { fieldname: "status", label: "Status", width: "120px" },
    ]);
  });

  it("leaves the list untouched when no column matches", () => {
    expect(applyColumnWidth(columns, "missing", "120px")).toEqual(columns);
  });
});

describe("clearColumnWidth", () => {
  const columns: Column[] = [
    { fieldname: "amount", label: "Amount", width: "8rem" },
    { fieldname: "status", label: "Status" },
  ];

  it("drops a fixed width back to auto so the column flexes again", () => {
    const cleared = clearColumnWidth(columns, "amount");
    expect(cleared).toEqual([
      { fieldname: "amount", label: "Amount" },
      { fieldname: "status", label: "Status" },
    ]);
    // serialize proves the cleared column is back to a flexing fr (leading = 2).
    expect(serializeColumns(cleared, FIELDS)[0].width).toBe(2);
  });

  it("no-ops on an already-auto column and on a missing one", () => {
    expect(clearColumnWidth(columns, "status")).toEqual(columns);
    expect(clearColumnWidth(columns, "missing")).toEqual(columns);
  });
});

describe("fetchFields", () => {
  const wire: WireColumn[] = [
    { key: "name", label: "Name", width: 2, align: "left", type: "Data" },
    {
      key: "_indicator",
      label: "Status",
      width: 1,
      align: "left",
      type: "Status",
    },
    { key: "status", label: "Status", width: 1, align: "left", type: "Select" },
  ];

  it("is `name` plus each column key, skipping declared synthetic keys (ADR-0033)", () => {
    // `_indicator` names no docfield, so requesting it would error get_list; the real
    // fields its cell reads are the host's concern (fetched separately). A re-added
    // subsumed field like `status` is a real docfield and stays.
    expect(fetchFields(wire, [{ key: "_indicator", label: "Status" }])).toEqual(
      ["name", "status"]
    );
  });

  it("fetches every column key when nothing is synthetic (byte-identical default)", () => {
    expect(fetchFields(wire)).toEqual(["name", "_indicator", "status"]);
  });
});

describe("dropOrphanedSyntheticColumns", () => {
  const layout: Column[] = [
    { fieldname: "name", label: "Name" },
    { fieldname: "_indicator", label: "Status" },
    { fieldname: "amount", label: "Amount" },
  ];

  it("drops a `_`-prefixed column no live declaration claims", () => {
    // The declaration was removed after the user customized; `_indicator` is orphaned.
    expect(dropOrphanedSyntheticColumns(layout, []).map((c) => c.fieldname)).toEqual(
      ["name", "amount"]
    );
  });

  it("keeps a `_`-prefixed column a live declaration still claims", () => {
    expect(
      dropOrphanedSyntheticColumns(layout, [{ key: "_indicator", label: "Status" }])
    ).toBe(layout);
  });

  it("returns the same reference when no column is synthetic (byte-identical)", () => {
    const docfields: Column[] = [
      { fieldname: "name", label: "Name" },
      { fieldname: "amount", label: "Amount" },
    ];
    expect(dropOrphanedSyntheticColumns(docfields, [])).toBe(docfields);
  });

  it("never drops a docfield column, even with no declarations", () => {
    expect(
      dropOrphanedSyntheticColumns(
        [{ fieldname: "amount", label: "Amount" }],
        []
      )
    ).toEqual([{ fieldname: "amount", label: "Amount" }]);
  });
});
