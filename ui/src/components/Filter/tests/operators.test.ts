import { describe, expect, it } from "vitest";
import { getOperators, isOptionField, defaultValueFor } from "../operators";
import type { FilterField } from "../types";

const values = (fieldtype: string, fieldname = "") =>
  getOperators(fieldtype, fieldname).map((o) => o.value);

const field = (fieldtype: string, options?: string): FilterField => ({
  label: "F",
  value: "f",
  fieldname: "f",
  fieldtype,
  options,
});

describe("getOperators", () => {
  it("offers the string operators for a Data field", () => {
    expect(values("Data")).toEqual([
      "equals",
      "not equals",
      "like",
      "not like",
      "in",
      "not in",
      "is",
    ]);
  });

  it("overrides to like/not like/is for the _assign field", () => {
    expect(values("Text", "_assign")).toEqual(["like", "not like", "is"]);
  });

  it("offers only equals for a Check field", () => {
    expect(values("Check")).toEqual(["equals"]);
  });

  it("adds comparison operators for a numeric field", () => {
    expect(values("Int")).toEqual([
      "equals",
      "not equals",
      "like",
      "not like",
      "in",
      "not in",
      "is",
      "<",
      ">",
      "<=",
      ">=",
    ]);
  });

  it("offers equals/in/is for a Select field", () => {
    expect(values("Select")).toEqual([
      "equals",
      "not equals",
      "in",
      "not in",
      "is",
    ]);
  });

  it("offers the Select operator set for an Autocomplete field", () => {
    expect(values("Autocomplete")).toEqual([
      "equals",
      "not equals",
      "in",
      "not in",
      "is",
    ]);
  });

  it("offers the link operators for a Link field", () => {
    expect(values("Link")).toEqual([
      "equals",
      "not equals",
      "like",
      "not like",
      "in",
      "not in",
      "is",
    ]);
  });

  it("offers the date operators incl. between and timespan for a Date field", () => {
    expect(values("Datetime")).toEqual([
      "equals",
      "not equals",
      "is",
      ">",
      "<",
      ">=",
      "<=",
      "between",
      "timespan",
    ]);
  });

  it("offers the like-family operators for a Duration field", () => {
    expect(values("Duration")).toEqual([
      "like",
      "not like",
      "in",
      "not in",
      "is",
    ]);
  });

  it("offers the rating operators for a Rating field", () => {
    expect(values("Rating")).toEqual([
      "equals",
      "not equals",
      ">",
      "<",
      ">=",
      "<=",
      "is",
    ]);
  });

  it("returns no operators for an unknown fieldtype", () => {
    expect(values("Geolocation")).toEqual([]);
  });
});

describe("isOptionField", () => {
  it("is true for fields whose `in`/`not in` picks from a known set", () => {
    expect(isOptionField("Select")).toBe(true);
    expect(isOptionField("Autocomplete")).toBe(true);
    expect(isOptionField("Link")).toBe(true);
  });

  it("is false for free-text, numeric, and Dynamic Link fields", () => {
    expect(isOptionField("Data")).toBe(false);
    expect(isOptionField("Int")).toBe(false);
    expect(isOptionField("Duration")).toBe(false);
    // Dynamic Link has no fixed target doctype to search.
    expect(isOptionField("Dynamic Link")).toBe(false);
  });
});

describe("defaultValueFor", () => {
  it("seeds is/is not with 'set'", () => {
    expect(defaultValueFor(field("Data"), "is")).toBe("set");
    expect(defaultValueFor(field("Data"), "is not")).toBe("set");
  });

  it("seeds in/not in with an empty list on an option field", () => {
    expect(defaultValueFor(field("Select", "Open\nClosed"), "in")).toEqual([]);
    expect(defaultValueFor(field("Link", "User"), "not in")).toEqual([]);
  });

  it("seeds in/not in with an empty string on a free-text field", () => {
    expect(defaultValueFor(field("Data"), "in")).toBe("");
  });

  it("falls back to the field's by-type default for other operators", () => {
    expect(defaultValueFor(field("Select", "Open\nClosed"), "equals")).toBe(
      "Open"
    );
    expect(defaultValueFor(field("Check"), "equals")).toBe("Yes");
  });
});
