import { describe, expect, it } from "vitest";
import { pickSiblingValue } from "../pickSiblingValue";

describe("pickSiblingValue", () => {
  it("prefers the row column, then the doc, then the parent doc", () => {
    const records = {
      row: { currency: "INR" },
      doc: { currency: "EUR" },
      parentDoc: { currency: "USD" },
    };
    expect(pickSiblingValue(records, "currency")).toBe("INR");
    expect(pickSiblingValue({ ...records, row: {} }, "currency")).toBe("EUR");
    expect(
      pickSiblingValue(
        { row: {}, doc: {}, parentDoc: { currency: "USD" } },
        "currency"
      )
    ).toBe("USD");
  });

  it("treats blank (undefined/null/'') as absent and defers to the next record", () => {
    expect(pickSiblingValue({ row: { x: "" }, doc: { x: "EUR" } }, "x")).toBe(
      "EUR"
    );
    expect(pickSiblingValue({ row: { x: null }, doc: { x: "EUR" } }, "x")).toBe(
      "EUR"
    );
  });

  it("returns undefined when no record carries the field", () => {
    expect(pickSiblingValue({ row: {}, doc: {} }, "missing")).toBeUndefined();
    expect(pickSiblingValue({}, "missing")).toBeUndefined();
  });
});
