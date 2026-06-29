import { describe, expect, it } from "vitest";
import {
  applyColumnWidth,
  getColumnAlign,
  parseColumns,
  serializeColumns,
} from "../columns";
import type { RawMetaField } from "../../FormLayout/types";
import type { Column } from "../types";

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

  it("defaults width to 10rem when a Column has none", () => {
    const [wire] = serializeColumns(
      [{ fieldname: "status", label: "Status" }],
      FIELDS
    );
    expect(wire.width).toBe("10rem");
    expect(wire.options).toBe("Open\nClosed");
    expect(wire.align).toBe("left");
  });

  it("falls back to a left-aligned Data column for fields absent from Meta", () => {
    const [wire] = serializeColumns(
      [{ fieldname: "name", label: "ID" }],
      FIELDS
    );
    expect(wire).toEqual({
      key: "name",
      label: "ID",
      width: "10rem",
      type: "Data",
      options: undefined,
      align: "left",
    });
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
