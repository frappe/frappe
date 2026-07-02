import { describe, expect, it } from "vitest";
import { getFilterableFields } from "../getFilterableFields";
import type { RawMetaField } from "../../FormLayout/types";

describe("getFilterableFields", () => {
  it("derives a filterable field from Meta, stamping label/value/fieldname", () => {
    const fields: RawMetaField[] = [
      { fieldname: "title", fieldtype: "Data", label: "Title" },
    ];
    const result = getFilterableFields(fields, "Lead");
    expect(result).toContainEqual({
      label: "Title",
      value: "title",
      fieldname: "title",
      fieldtype: "Data",
      options: undefined,
    });
  });

  it("keeps an Autocomplete field with its options for multi-select filtering", () => {
    const result = getFilterableFields(
      [
        {
          fieldname: "source",
          fieldtype: "Autocomplete",
          label: "Source",
          options: "Web\nReferral",
        },
      ],
      "Lead"
    );
    expect(result.find((f) => f.fieldname === "source")?.options).toBe(
      "Web\nReferral"
    );
  });

  it("drops fields whose fieldtype is not filterable", () => {
    const fields: RawMetaField[] = [
      { fieldname: "sec", fieldtype: "Section Break" },
      { fieldname: "kids", fieldtype: "Table", options: "Child" },
      { fieldname: "title", fieldtype: "Data", label: "Title" },
    ];
    const names = getFilterableFields(fields, "Lead").map((f) => f.fieldname);
    expect(names).toContain("title");
    expect(names).not.toContain("sec");
    expect(names).not.toContain("kids");
  });

  it("prepends the standard fields ahead of meta fields", () => {
    const result = getFilterableFields(
      [{ fieldname: "title", fieldtype: "Data", label: "Title" }],
      "Lead"
    );
    const names = result.map((f) => f.fieldname);
    expect(names.slice(0, 9)).toEqual([
      "name",
      "owner",
      "modified_by",
      "_user_tags",
      "_liked_by",
      "_comments",
      "_assign",
      "creation",
      "modified",
    ]);
    expect(names[names.length - 1]).toBe("title");
  });

  it("carries Select options through for fieldtype-aware value inputs", () => {
    const result = getFilterableFields(
      [
        {
          fieldname: "status",
          fieldtype: "Select",
          label: "Status",
          options: "Open\nClosed",
        },
      ],
      "Lead"
    );
    expect(result.find((f) => f.fieldname === "status")?.options).toBe(
      "Open\nClosed"
    );
  });

  it("stamps the doctype as the name field's Link target so Name filters search its records", () => {
    const result = getFilterableFields([], "CRM Lead");
    expect(result.find((f) => f.fieldname === "name")?.options).toBe(
      "CRM Lead"
    );
  });
});
