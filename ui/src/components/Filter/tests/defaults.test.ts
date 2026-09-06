import { describe, expect, it } from "vitest";
import { getDefaultOperator, getDefaultValue } from "../operators";
import type { FilterField } from "../types";

const field = (fieldtype: string, options?: string): FilterField => ({
  label: "F",
  value: "f",
  fieldname: "f",
  fieldtype,
  options,
});

describe("getDefaultOperator", () => {
  it("defaults Select/Check/Number fields to equals", () => {
    expect(getDefaultOperator("Select")).toBe("equals");
    expect(getDefaultOperator("Check")).toBe("equals");
    expect(getDefaultOperator("Int")).toBe("equals");
  });

  it("defaults Date fields to between", () => {
    expect(getDefaultOperator("Datetime")).toBe("between");
  });

  it("defaults everything else to like", () => {
    expect(getDefaultOperator("Data")).toBe("like");
  });
});

describe("getDefaultValue", () => {
  it("seeds a Select field with its first option", () => {
    expect(getDefaultValue(field("Select", "Open\nClosed"))).toBe("Open");
  });

  it("seeds a Check field with Yes", () => {
    expect(getDefaultValue(field("Check"))).toBe("Yes");
  });

  it("seeds a Date field with null", () => {
    expect(getDefaultValue(field("Date"))).toBeNull();
  });

  it("seeds everything else with an empty string", () => {
    expect(getDefaultValue(field("Data"))).toBe("");
  });
});
