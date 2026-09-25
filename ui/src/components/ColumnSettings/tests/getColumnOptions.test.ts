import { describe, expect, it } from "vitest";
import { getColumnOptions } from "../getColumnOptions";

const STANDARD = [
  { label: "Name", value: "name", fieldname: "name" },
  { label: "Last Modified", value: "modified", fieldname: "modified" },
  { label: "Created On", value: "creation", fieldname: "creation" },
  { label: "Modified By", value: "modified_by", fieldname: "modified_by" },
  { label: "Owner", value: "owner", fieldname: "owner" },
];

describe("getColumnOptions", () => {
  it("maps a data field to a {label, value, fieldname} option, then appends the standard fields", () => {
    expect(
      getColumnOptions([
        { fieldname: "status", fieldtype: "Select", label: "Status" },
      ])
    ).toEqual([
      { label: "Status", value: "status", fieldname: "status" },
      ...STANDARD,
    ]);
  });

  it("excludes layout/no-data fieldtypes and child tables", () => {
    const result = getColumnOptions([
      { fieldname: "sb", fieldtype: "Section Break", label: "Sec" },
      { fieldname: "cb", fieldtype: "Column Break" },
      { fieldname: "tb", fieldtype: "Tab Break", label: "Tab" },
      { fieldname: "html", fieldtype: "HTML", label: "Html" },
      { fieldname: "head", fieldtype: "Heading", label: "Head" },
      { fieldname: "btn", fieldtype: "Button", label: "Btn" },
      { fieldname: "fold", fieldtype: "Fold" },
      { fieldname: "items", fieldtype: "Table", label: "Items" },
      { fieldname: "tags", fieldtype: "Table MultiSelect", label: "Tags" },
      { fieldname: "title", fieldtype: "Data", label: "Title" },
    ]);
    expect(result).toEqual([
      { label: "Title", value: "title", fieldname: "title" },
      ...STANDARD,
    ]);
  });

  it("appends declared synthetic columns so a hidden one is re-addable (ADR-0033)", () => {
    expect(
      getColumnOptions(
        [{ fieldname: "status", fieldtype: "Select", label: "Status" }],
        [{ key: "_indicator", label: "Status", type: "Status" }]
      )
    ).toEqual([
      { label: "Status", value: "status", fieldname: "status" },
      ...STANDARD,
      { label: "Status", value: "_indicator", fieldname: "_indicator" },
    ]);
  });
});
