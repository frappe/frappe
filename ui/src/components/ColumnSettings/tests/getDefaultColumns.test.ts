import { describe, expect, it } from "vitest";
import { getDefaultColumns, foldSyntheticColumns } from "../getDefaultColumns";
import type { Column } from "../types";

describe("getDefaultColumns", () => {
  it("maps the in_list_view fields to Columns, prepending Name", () => {
    expect(
      getDefaultColumns([
        {
          fieldname: "status",
          fieldtype: "Select",
          label: "Status",
          in_list_view: 1,
        },
        {
          fieldname: "amount",
          fieldtype: "Currency",
          label: "Amount",
          in_list_view: 1,
        },
        { fieldname: "notes", fieldtype: "Text", label: "Notes" },
      ])
    ).toEqual([
      { fieldname: "name", label: "Name" },
      { fieldname: "status", label: "Status" },
      { fieldname: "amount", label: "Amount" },
    ]);
  });

  it("falls back to the field's name when it has no label", () => {
    expect(
      getDefaultColumns([
        { fieldname: "custom_x", fieldtype: "Data", in_list_view: 1 },
      ])
    ).toEqual([
      { fieldname: "name", label: "Name" },
      { fieldname: "custom_x", label: "custom_x" },
    ]);
  });

  it("yields just Name when no field is flagged in_list_view", () => {
    expect(
      getDefaultColumns([
        { fieldname: "notes", fieldtype: "Text", label: "Notes" },
      ])
    ).toEqual([{ fieldname: "name", label: "Name" }]);
  });

  it("leads with the title_field column instead of Name when set", () => {
    expect(
      getDefaultColumns(
        [
          {
            fieldname: "subject",
            fieldtype: "Data",
            label: "Subject",
          },
          {
            fieldname: "status",
            fieldtype: "Select",
            label: "Status",
            in_list_view: 1,
          },
        ],
        "subject"
      )
    ).toEqual([
      { fieldname: "subject", label: "Subject" },
      { fieldname: "status", label: "Status" },
    ]);
  });

  it("drops the title_field from the in_list_view tail so it isn't listed twice", () => {
    expect(
      getDefaultColumns(
        [
          {
            fieldname: "subject",
            fieldtype: "Data",
            label: "Subject",
            in_list_view: 1,
          },
          {
            fieldname: "status",
            fieldtype: "Select",
            label: "Status",
            in_list_view: 1,
          },
        ],
        "subject"
      )
    ).toEqual([
      { fieldname: "subject", label: "Subject" },
      { fieldname: "status", label: "Status" },
    ]);
  });

  it("falls back to Name when title_field names a field absent from Meta", () => {
    expect(
      getDefaultColumns(
        [
          {
            fieldname: "status",
            fieldtype: "Select",
            label: "Status",
            in_list_view: 1,
          },
        ],
        "missing_field"
      )
    ).toEqual([
      { fieldname: "name", label: "Name" },
      { fieldname: "status", label: "Status" },
    ]);
  });
});

describe("foldSyntheticColumns", () => {
  const defaults: Column[] = [
    { fieldname: "subject", label: "Subject" },
    { fieldname: "status", label: "Status" },
    { fieldname: "modified", label: "Modified" },
  ];

  it("appends a synthetic column at the end by default", () => {
    expect(
      foldSyntheticColumns(defaults, [{ key: "_indicator", label: "Status" }])
    ).toEqual([...defaults, { fieldname: "_indicator", label: "Status" }]);
  });

  it("inserts an `after-title` column right after the leading column", () => {
    expect(
      foldSyntheticColumns(defaults, [
        { key: "_indicator", label: "Status", place: "after-title" },
      ]).map((c) => c.fieldname)
    ).toEqual(["subject", "_indicator", "status", "modified"]);
  });

  it("prepends a `start` column before the leading column", () => {
    expect(
      foldSyntheticColumns(defaults, [
        { key: "_flag", label: "Flag", place: "start" },
      ]).map((c) => c.fieldname)
    ).toEqual(["_flag", "subject", "status", "modified"]);
  });

  it("keeps declaration order for multiple columns sharing the `after-title` anchor", () => {
    // A host declaring a flag then a status badge, both after-title, must see them in
    // that order — not reversed by inserting each at the same fixed index.
    expect(
      foldSyntheticColumns(defaults, [
        { key: "_flag", label: "Flag", place: "after-title" },
        { key: "_indicator", label: "Status", place: "after-title" },
      ]).map((c) => c.fieldname)
    ).toEqual(["subject", "_flag", "_indicator", "status", "modified"]);
  });

  it("keeps declaration order for multiple `start` columns", () => {
    expect(
      foldSyntheticColumns(defaults, [
        { key: "_a", label: "A", place: "start" },
        { key: "_b", label: "B", place: "start" },
      ]).map((c) => c.fieldname)
    ).toEqual(["_a", "_b", "subject", "status", "modified"]);
  });

  it("drops the docfield a declaration subsumes from the seed", () => {
    expect(
      foldSyntheticColumns(defaults, [
        {
          key: "_indicator",
          label: "Status",
          place: "after-title",
          subsumes: "status",
        },
      ]).map((c) => c.fieldname)
    ).toEqual(["subject", "_indicator", "modified"]);
  });

  it("carries the declaration's default width onto the folded column", () => {
    expect(
      foldSyntheticColumns(defaults, [
        { key: "_indicator", label: "Status", width: "8rem" },
      ]).at(-1)
    ).toEqual({ fieldname: "_indicator", label: "Status", width: "8rem" });
  });

  it("returns the seed untouched (same reference) when no column is declared", () => {
    expect(foldSyntheticColumns(defaults, [])).toBe(defaults);
  });
});
