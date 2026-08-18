import { describe, expect, it } from "vitest";
import {
  DEFAULT_NUMBER_FORMAT,
  flt,
  formatCurrency,
  formatField,
  formatNumber,
  getCurrencySymbol,
  getNumberFormatInfo,
} from "../formatNumber";

describe("getNumberFormatInfo", () => {
  it("derives separators and precision from the default format", () => {
    expect(getNumberFormatInfo("#,###.##")).toEqual({
      decimalStr: ".",
      groupSep: ",",
      precision: 2,
    });
  });

  it("derives the european format (swapped separators)", () => {
    expect(getNumberFormatInfo("#.###,##")).toEqual({
      decimalStr: ",",
      groupSep: ".",
      precision: 2,
    });
  });

  it("returns a fresh object (does not mutate a shared map)", () => {
    const a = getNumberFormatInfo("#,###.##");
    a.precision = 99;
    expect(getNumberFormatInfo("#,###.##").precision).toBe(2);
  });

  it("falls back to dot/comma for an unknown format", () => {
    expect(getNumberFormatInfo("weird")).toMatchObject({
      decimalStr: ".",
      groupSep: ",",
    });
  });
});

describe("formatNumber", () => {
  it("groups thousands and applies default precision", () => {
    expect(formatNumber(1234567.5)).toBe("1,234,567.50");
  });

  it("honours an explicit precision", () => {
    expect(formatNumber(1234.7, { precision: 0 })).toBe("1,235");
    expect(formatNumber(1234.567, { precision: 3 })).toBe("1,234.567");
  });

  it("uses Banker’s (round-half-to-even) rounding by default", () => {
    expect(formatNumber(1234.5, { precision: 0 })).toBe("1,234"); // 1234 is even
    expect(formatNumber(1235.5, { precision: 0 })).toBe("1,236"); // 1236 is even
  });

  it("formats with the european locale (dot groups, comma decimal)", () => {
    expect(formatNumber(1234567.5, { numberFormat: "#.###,##" })).toBe(
      "1.234.567,50"
    );
  });

  it("formats negatives and zero", () => {
    expect(formatNumber(-1234.5)).toBe("-1,234.50");
    expect(formatNumber(0)).toBe("0.00");
  });

  it("uses Indian grouping for #,##,###.##", () => {
    expect(formatNumber(1234567, { numberFormat: "#,##,###.##" })).toBe(
      "12,34,567.00"
    );
  });

  it("rounds to the requested precision", () => {
    expect(formatNumber(2.345, { precision: 2 })).toBe("2.35");
  });
});

describe("getCurrencySymbol", () => {
  it("resolves a known currency code", () => {
    expect(getCurrencySymbol("USD")).toBe("$");
    expect(getCurrencySymbol("EUR")).toBe("€");
  });

  it("returns null for an invalid code", () => {
    expect(getCurrencySymbol("NOTACODE")).toBeNull();
  });
});

describe("formatCurrency", () => {
  it("prefixes the currency symbol with default precision 2", () => {
    expect(formatCurrency(1234.5, { currency: "USD" })).toBe("$ 1,234.50");
  });

  it("omits the symbol when no currency is given", () => {
    expect(formatCurrency(1234.5)).toBe("1,234.50");
  });

  it("omits the symbol for an unresolvable currency", () => {
    expect(formatCurrency(1000, { currency: "NOTACODE" })).toBe("1,000.00");
  });

  it("honours an explicit precision", () => {
    expect(formatCurrency(1234.567, { currency: "USD", precision: 3 })).toBe(
      "$ 1,234.567"
    );
  });
});

describe("flt", () => {
  it("returns 0 for null/empty", () => {
    expect(flt(null)).toBe(0);
    expect(flt("")).toBe(0);
  });

  it("passes numbers through unrounded by default", () => {
    expect(flt(1234.567)).toBe(1234.567);
  });

  it("strips group separators back to a Number", () => {
    expect(flt("1,234,567.50")).toBe(1234567.5);
  });

  it("parses the european locale", () => {
    expect(flt("1.234.567,50", { numberFormat: "#.###,##" })).toBe(1234567.5);
  });

  it("strips a leading currency symbol", () => {
    expect(flt("$ 1,234.50")).toBe(1234.5);
  });

  it("rounds when a precision is supplied", () => {
    expect(flt(2.345, { precision: 2 })).toBe(2.35);
  });

  it("round-trips formatNumber output", () => {
    const formatted = formatNumber(98765.43);
    expect(flt(formatted)).toBe(98765.43);
  });
});

describe("formatField", () => {
  it("formats Int as a plain integer — no grouping, no decimals (matches Frappe cint)", () => {
    expect(formatField(1234.7, { fieldtype: "Int" })).toBe("1234");
    expect(formatField(1234567, { fieldtype: "Int" })).toBe("1234567");
    // A site number_format (grouping/european) must not affect Int.
    expect(
      formatField(1234567, { fieldtype: "Int", numberFormat: "#.###,##" })
    ).toBe("1234567");
  });

  it("formats Float with derived/explicit precision", () => {
    expect(formatField(1234.5, { fieldtype: "Float" })).toBe("1,234.50");
    expect(formatField(1234.567, { fieldtype: "Float", precision: 3 })).toBe(
      "1,234.567"
    );
  });

  it("formats Currency with a resolved symbol", () => {
    expect(
      formatField(1234.5, { fieldtype: "Currency", currency: "USD" })
    ).toBe("$ 1,234.50");
  });

  it("formats Currency without a symbol when none resolved", () => {
    expect(formatField(1234.5, { fieldtype: "Currency" })).toBe("1,234.50");
  });

  it("appends % for Percent", () => {
    expect(formatField(42.5, { fieldtype: "Percent", precision: 1 })).toBe(
      "42.5%"
    );
  });

  it("falls back to plain number for an unknown/blank fieldtype", () => {
    expect(formatField(1234.5)).toBe("1,234.50");
  });

  it("returns empty string for null/empty", () => {
    expect(formatField(null, { fieldtype: "Currency", currency: "USD" })).toBe(
      ""
    );
    expect(formatField("", { fieldtype: "Int" })).toBe("");
  });

  it("honours a non-default numberFormat", () => {
    expect(
      formatField(1234.5, { fieldtype: "Float", numberFormat: "#.###,##" })
    ).toBe("1.234,50");
  });
});

describe("DEFAULT_NUMBER_FORMAT", () => {
  it("is Frappe’s default", () => {
    expect(DEFAULT_NUMBER_FORMAT).toBe("#,###.##");
  });
});
