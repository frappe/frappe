import { describe, expect, it } from "vitest";
import { parseFilters, serializeFilters } from "../filters";
import type { FilterField } from "../types";

const STATUS: FilterField = {
  label: "Status",
  value: "status",
  fieldname: "status",
  fieldtype: "Select",
  options: "Open\nClosed",
};
const ACTIVE: FilterField = {
  label: "Active",
  value: "is_active",
  fieldname: "is_active",
  fieldtype: "Check",
};
const TITLE: FilterField = {
  label: "Title",
  value: "title",
  fieldname: "title",
  fieldtype: "Data",
};

describe("serializeFilters", () => {
  it("serializes a single equals condition to a bare wire value", () => {
    expect(
      serializeFilters([
        { fieldname: "status", operator: "equals", value: "Open" },
      ])
    ).toEqual({ status: "Open" });
  });

  it("maps a like condition to a wire operator pair and wraps the value in %", () => {
    expect(
      serializeFilters([
        { fieldname: "title", operator: "like", value: "acme" },
      ])
    ).toEqual({ title: ["LIKE", "%acme%"] });
  });

  it("splits a comma string into a trimmed array for an in condition", () => {
    expect(
      serializeFilters([
        { fieldname: "status", operator: "in", value: "Open, Closed" },
      ])
    ).toEqual({ status: ["in", ["Open", "Closed"]] });
  });

  it("maps a Yes/No equals value to a boolean (Check field)", () => {
    expect(
      serializeFilters([
        { fieldname: "is_active", operator: "equals", value: "Yes" },
      ])
    ).toEqual({ is_active: true });
    expect(
      serializeFilters([
        { fieldname: "is_active", operator: "equals", value: "No" },
      ])
    ).toEqual({ is_active: false });
  });

  it("serializes multiple conditions into one wire dict", () => {
    expect(
      serializeFilters([
        { fieldname: "status", operator: "equals", value: "Open" },
        { fieldname: "title", operator: "like", value: "acme" },
      ])
    ).toEqual({ status: "Open", title: ["LIKE", "%acme%"] });
  });
});

describe("parseFilters", () => {
  it("parses a bare wire value into an equals condition with its field attached", () => {
    expect(parseFilters([STATUS], { status: "Open" })).toEqual([
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ]);
  });

  it("surfaces a bare Check boolean as a Yes/No equals condition", () => {
    expect(parseFilters([ACTIVE], { is_active: true })).toEqual([
      {
        field: ACTIVE,
        fieldname: "is_active",
        operator: "equals",
        value: "Yes",
      },
    ]);
    expect(parseFilters([ACTIVE], { is_active: false })).toEqual([
      {
        field: ACTIVE,
        fieldname: "is_active",
        operator: "equals",
        value: "No",
      },
    ]);
  });

  it("maps an operator pair back to its UI operator", () => {
    expect(parseFilters([TITLE], { title: ["LIKE", "%acme%"] })).toEqual([
      { field: TITLE, fieldname: "title", operator: "like", value: "%acme%" },
    ]);
  });

  it("drops a wire entry whose field is absent from Meta", () => {
    expect(parseFilters([STATUS], { status: "Open", gone: "x" })).toEqual([
      { field: STATUS, fieldname: "status", operator: "equals", value: "Open" },
    ]);
  });
});
