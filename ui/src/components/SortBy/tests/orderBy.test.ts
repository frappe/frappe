import { describe, expect, it } from "vitest";
import { parseOrderBy, serializeOrderBy } from "../orderBy";

describe("parseOrderBy", () => {
  it("parses a single ordering rule", () => {
    expect(parseOrderBy("modified desc")).toEqual([
      { fieldname: "modified", direction: "desc" },
    ]);
  });

  it("parses multiple comma-joined rules in order", () => {
    expect(parseOrderBy("modified desc, name asc")).toEqual([
      { fieldname: "modified", direction: "desc" },
      { fieldname: "name", direction: "asc" },
    ]);
  });

  it("returns no Sorts for an empty or whitespace string", () => {
    expect(parseOrderBy("")).toEqual([]);
    expect(parseOrderBy("   ")).toEqual([]);
  });

  it("defaults a directionless rule to ascending", () => {
    expect(parseOrderBy("name")).toEqual([
      { fieldname: "name", direction: "asc" },
    ]);
  });
});

describe("serializeOrderBy", () => {
  it("joins Sorts into a Frappe order_by string", () => {
    expect(
      serializeOrderBy([
        { fieldname: "modified", direction: "desc" },
        { fieldname: "name", direction: "asc" },
      ])
    ).toBe("modified desc, name asc");
  });

  it("serializes an empty list to an empty string", () => {
    expect(serializeOrderBy([])).toBe("");
  });

  it("round-trips with parseOrderBy", () => {
    const orderBy = "status asc, modified desc";
    expect(serializeOrderBy(parseOrderBy(orderBy))).toBe(orderBy);
  });
});
