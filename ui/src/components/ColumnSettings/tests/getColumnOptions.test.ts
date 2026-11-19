import { describe, expect, it } from "vitest";
import { getColumnOptions } from "../getColumnOptions";

const STANDARD = [
  { label: "Name", value: "name", fieldname: "name" },
  { label: "Last Modified", value: "modified", fieldname: "modified" },
  { label: "Created On", value: "creation", fieldname: "creation" },
  { label: "Modified By", value: "modified_by", fieldname: "modified_by" },
  { label: "Owner", value: "owner", fieldname: "owner" },
];

const COLLAB = [
  { label: "Assigned To", value: "_assign", fieldname: "_assign" },
  { label: "Favourite", value: "_favourite", fieldname: "_favourite" },
  { label: "Tags", value: "_user_tags", fieldname: "_user_tags" },
  { label: "Comments", value: "_comments", fieldname: "_comments" },
  { label: "Liked By", value: "_liked_by", fieldname: "_liked_by" },
];
const DOCSTATUS = { label: "Document Status", value: "docstatus", fieldname: "docstatus" };

describe("getColumnOptions", () => {
  it("offers Document Status only on a submittable doctype", () => {
    const names = (meta = {}) => getColumnOptions([], [], meta).map((o) => o.fieldname);
    expect(names()).not.toContain("docstatus");
    expect(names({ is_submittable: 1 })).toContain("docstatus");
  });

  it("offers no collaboration column on a virtual doctype", () => {
    const options = getColumnOptions([], [], { is_virtual: 1, is_submittable: 1 });
    expect(options).toEqual(STANDARD);
  });

  it("maps a data field to a {label, value, fieldname} option, then appends the standard fields", () => {
    expect(
      getColumnOptions([
        { fieldname: "status", fieldtype: "Select", label: "Status" },
      ])
    ).toEqual([
      { label: "Status", value: "status", fieldname: "status" },
      ...STANDARD,
      ...COLLAB,
    ]);
  });

  it("excludes layout/no-data fieldtypes, child tables and Image/Attachment Gallery", () => {
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
      { fieldname: "photo", fieldtype: "Image", label: "Photo" },
      { fieldname: "gallery", fieldtype: "Attachment Gallery", label: "Gallery" },
      { fieldname: "title", fieldtype: "Data", label: "Title" },
    ]);
    expect(result).toEqual([
      { label: "Title", value: "title", fieldname: "title" },
      ...STANDARD,
      ...COLLAB,
    ]);
  });

  it("appends declared synthetic columns so a hidden one is re-addable", () => {
    expect(
      getColumnOptions(
        [{ fieldname: "status", fieldtype: "Select", label: "Status" }],
        [{ key: "_indicator", label: "Status", type: "Status" }]
      )
    ).toEqual([
      { label: "Status", value: "status", fieldname: "status" },
      ...STANDARD,
      ...COLLAB,
      { label: "Status", value: "_indicator", fieldname: "_indicator" },
    ]);
  });
});
