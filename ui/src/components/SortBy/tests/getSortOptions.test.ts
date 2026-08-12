import { describe, expect, it } from "vitest";
import { getSortOptions } from "../getSortOptions";

const STANDARD = [
  { label: "Name", value: "name", fieldname: "name" },
  { label: "Created On", value: "creation", fieldname: "creation" },
  { label: "Last Modified", value: "modified", fieldname: "modified" },
  { label: "Modified By", value: "modified_by", fieldname: "modified_by" },
  { label: "Owner", value: "owner", fieldname: "owner" },
];

describe("getSortOptions", () => {
  it("maps a value field to a {label, value, fieldname} option", () => {
    expect(
      getSortOptions([
        { fieldname: "status", fieldtype: "Select", label: "Status" },
      ])
    ).toEqual([
      { label: "Status", value: "status", fieldname: "status" },
      ...STANDARD,
    ]);
  });

  it("drops no-value fieldtypes and label-less fields", () => {
    const result = getSortOptions([
      { fieldname: "sb", fieldtype: "Section Break" },
      { fieldname: "items", fieldtype: "Table", label: "Items" },
      { fieldname: "logo", fieldtype: "Image", label: "Logo" },
      { fieldname: "nolabel", fieldtype: "Data" },
      { fieldname: "title", fieldtype: "Data", label: "Title" },
    ]);
    expect(result).toEqual([
      { label: "Title", value: "title", fieldname: "title" },
      ...STANDARD,
    ]);
  });
});
