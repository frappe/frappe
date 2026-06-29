import { describe, expect, it } from "vitest";
import { carryOver, conditionFor } from "../operators";
import type {
  Filter,
  FilterField,
  FilterOperator,
  FilterValue,
} from "../types";

const field = (
  fieldname: string,
  fieldtype: string,
  options?: string
): FilterField => ({
  label: fieldname,
  value: fieldname,
  fieldname,
  fieldtype,
  options,
});

const condition = (
  f: FilterField,
  operator: FilterOperator,
  value: FilterValue
): Filter => ({ field: f, fieldname: f.fieldname, operator, value });

describe("conditionFor", () => {
  it("seeds a fresh condition from the field's defaults", () => {
    expect(conditionFor(field("status", "Select", "Open\nClosed"))).toEqual({
      field: field("status", "Select", "Open\nClosed"),
      fieldname: "status",
      operator: "equals",
      value: "Open",
    });
  });
});

describe("carryOver — operator", () => {
  it("keeps the operator when the new field still offers it", () => {
    const prev = condition(
      field("status", "Select", "Open\nClosed"),
      "equals",
      "Open"
    );
    const next = carryOver(prev, field("priority", "Select", "High\nLow"));
    expect(next.operator).toBe("equals");
  });

  it("falls back to the new field's default operator when it doesn't", () => {
    // Data offers `like`; Date does not, so it resets to Date's default `between`.
    const prev = condition(field("subject", "Data"), "like", "hi");
    const next = carryOver(prev, field("created", "Date"));
    expect(next.operator).toBe("between");
    expect(next.value).toBeNull();
  });
});

describe("carryOver — value", () => {
  it("carries a free-text value across like/in operators", () => {
    const prev = condition(field("first_name", "Data"), "like", "john");
    const next = carryOver(prev, field("last_name", "Data"));
    expect(next).toMatchObject({ operator: "like", value: "john" });
  });

  it("carries an operator-driven set/not-set value to any field", () => {
    const prev = condition(field("first_name", "Data"), "is", "set");
    const next = carryOver(prev, field("amount", "Currency"));
    expect(next).toMatchObject({ operator: "is", value: "set" });
  });

  it("drops the value when the new field is a different value domain", () => {
    // Both fields offer `equals`, but a number is meaningless in a Link input.
    const prev = condition(field("amount", "Currency"), "equals", "100");
    const next = carryOver(prev, field("customer", "Link", "Customer"));
    expect(next).toMatchObject({ operator: "equals", value: "" });
  });

  it("carries a Select value only when it exists in the new field's options", () => {
    const prev = condition(
      field("status", "Select", "Open\nClosed"),
      "equals",
      "Open"
    );
    expect(carryOver(prev, field("stage", "Select", "Open\nWon")).value).toBe(
      "Open"
    );
    expect(carryOver(prev, field("stage", "Select", "High\nLow")).value).toBe(
      "High"
    );
  });

  it("resets an `in` option list to empty when the field changes", () => {
    // The picked options belong to `status`; they're meaningless on `priority`.
    const prev = condition(field("status", "Select", "Open\nClosed"), "in", [
      "Open",
      "Closed",
    ]);
    expect(
      carryOver(prev, field("priority", "Select", "High\nLow"))
    ).toMatchObject({ operator: "in", value: [] });
  });

  it("carries an `in` Link list when the target doctype matches", () => {
    const prev = condition(field("owner", "Link", "User"), "in", [
      "a@x.io",
      "b@x.io",
    ]);
    expect(carryOver(prev, field("modified_by", "Link", "User")).value).toEqual(
      ["a@x.io", "b@x.io"]
    );
    expect(
      carryOver(prev, field("customer", "Link", "Customer")).value
    ).toEqual([]);
  });

  it("carries a Link value only when the target doctype matches", () => {
    const prev = condition(
      field("owner", "Link", "User"),
      "equals",
      "admin@x.io"
    );
    expect(carryOver(prev, field("modified_by", "Link", "User")).value).toBe(
      "admin@x.io"
    );
    expect(carryOver(prev, field("customer", "Link", "Customer")).value).toBe(
      ""
    );
  });
});
