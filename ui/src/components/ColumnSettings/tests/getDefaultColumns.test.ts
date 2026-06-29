import { describe, expect, it } from "vitest";
import { getDefaultColumns } from "../getDefaultColumns";

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
});
