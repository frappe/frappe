import { describe, expect, it } from "vitest";
import { getOperators } from "../operators";

const values = (fieldtype: string, fieldname = "") =>
  getOperators(fieldtype, fieldname).map((o) => o.value);

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
