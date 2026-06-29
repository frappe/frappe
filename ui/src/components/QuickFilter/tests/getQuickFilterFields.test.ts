import { describe, expect, it } from "vitest";
import { getQuickFilterFields } from "../getQuickFilterFields";
import type { RawMetaField } from "../../FormLayout/types";

const fields: RawMetaField[] = [
  {
    fieldname: "status",
    fieldtype: "Select",
    label: "Status",
    in_standard_filter: 1,
  },
  {
    fieldname: "customer",
    fieldtype: "Link",
    label: "Customer",
    options: "Customer",
    in_standard_filter: 1,
  },
  { fieldname: "notes", fieldtype: "Text", label: "Notes" },
  {
    fieldname: "title",
    fieldtype: "Data",
    label: "Title",
    in_standard_filter: 0,
  },
];

describe("getQuickFilterFields", () => {
  it("keeps only in_standard_filter fields, mapped to FilterField shape", () => {
    expect(getQuickFilterFields(fields)).toEqual([
      {
        label: "Status",
        value: "status",
        fieldname: "status",
        fieldtype: "Select",
        options: undefined,
      },
      {
        label: "Customer",
        value: "customer",
        fieldname: "customer",
        fieldtype: "Link",
        options: "Customer",
      },
    ]);
  });

  it("does not surface name by default (only via the customize picker)", () => {
    const result = getQuickFilterFields(fields);
    expect(result.some((f) => f.fieldname === "name")).toBe(false);
  });

  it("falls back to the fieldname when a flagged field has no label", () => {
    const [field] = getQuickFilterFields([
      { fieldname: "priority", fieldtype: "Select", in_standard_filter: 1 },
    ]);
    expect(field.label).toBe("priority");
  });

  it("returns an empty list when nothing is flagged", () => {
    expect(
      getQuickFilterFields([{ fieldname: "x", fieldtype: "Data" }])
    ).toEqual([]);
  });
});
