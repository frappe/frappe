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
  it("prepends name, then the in_standard_filter fields in FilterField shape", () => {
    expect(getQuickFilterFields(fields, "Sales Order")).toEqual([
      {
        label: "Name",
        value: "name",
        fieldname: "name",
        fieldtype: "Link",
        options: "Sales Order",
      },
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

  it("surfaces name first, as a self-Link against the doctype", () => {
    const [first] = getQuickFilterFields(fields, "Sales Order");
    expect(first.fieldname).toBe("name");
    expect(first.options).toBe("Sales Order");
  });

  it("falls back to the fieldname when a flagged field has no label", () => {
    const [, field] = getQuickFilterFields(
      [{ fieldname: "priority", fieldtype: "Select", in_standard_filter: 1 }],
      "Sales Order"
    );
    expect(field.label).toBe("priority");
  });

  it("returns just name when nothing is flagged", () => {
    expect(
      getQuickFilterFields([{ fieldname: "x", fieldtype: "Data" }], "Sales Order")
    ).toEqual([
      {
        label: "Name",
        value: "name",
        fieldname: "name",
        fieldtype: "Link",
        options: "Sales Order",
      },
    ]);
  });
});
