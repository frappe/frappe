import { afterEach, describe, expect, it, vi } from "vitest";

// Stub frappe-ui so the module imports cleanly in vitest's node env (the
// built-in reader is never reached here — `window` is undefined, so
// `builtinGetDocValue` returns undefined without touching frappe-ui).
vi.mock("frappe-ui", () => ({
  createResource: vi.fn(),
  getCachedResource: vi.fn(() => null),
}));

import {
  resolveFieldCurrency,
  setDocValueReader,
  resetDocValueReader,
  getDocValueReader,
} from "../resolveCurrency";

afterEach(() => resetDocValueReader());

describe("resolveFieldCurrency", () => {
  // 1. No options → site default.
  it("falls back to the default currency when there are no options", () => {
    expect(resolveFieldCurrency(undefined, { defaultCurrency: "USD" })).toBe(
      "USD"
    );
    expect(resolveFieldCurrency("", { defaultCurrency: "USD" })).toBe("USD");
  });

  it("returns undefined when nothing resolves and there is no default", () => {
    expect(resolveFieldCurrency(undefined)).toBeUndefined();
    expect(resolveFieldCurrency("currency", { doc: {} })).toBeUndefined();
  });

  // 2. options = sibling fieldname on the doc.
  it("reads the currency from the named sibling field on the doc", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
  });

  it("falls back to the default when the sibling field is empty", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "" },
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  // 3. Child-table cell: row wins, then doc, then default.
  it("prefers the row column over the doc for a grid cell", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: { currency: "INR" },
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("INR");
  });

  it("falls back to the doc when the row column is empty/absent", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: { currency: "" },
        doc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
    expect(
      resolveFieldCurrency("currency", { row: {}, doc: { currency: "EUR" } })
    ).toBe("EUR");
  });

  it("falls back to the default when neither row nor doc has the currency", () => {
    expect(
      resolveFieldCurrency("currency", {
        row: {},
        doc: {},
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  // 3b. Row dialog: the row's own doc has no sibling, so the parent doc supplies
  // it — keeps the dialog's currency in sync with the grid (where the parent doc
  // is the injected `doc`).
  it("falls back to the parent doc when the row/doc lack the currency", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "" },
        parentDoc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("EUR");
  });

  it("prefers a child-local sibling over the parent doc", () => {
    expect(
      resolveFieldCurrency("currency", {
        doc: { currency: "INR" },
        parentDoc: { currency: "EUR" },
        defaultCurrency: "USD",
      })
    ).toBe("INR");
  });

  it("resolves the cross-record link docname from the parent doc as a last resort", () => {
    const getDocValue = (_dt: string, name: string) =>
      name === "ParentCo" ? "JPY" : "USD";
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: {},
        parentDoc: { company: "ParentCo" },
        getDocValue,
      })
    ).toBe("JPY");
  });

  // 4. Cross-record "Doctype:link_field:currency_field" form.
  it("reads the currency off the linked record via an explicit getDocValue", () => {
    const getDocValue = (dt: string, name: string, field: string) =>
      dt === "Company" && name === "Acme" && field === "default_currency"
        ? "GBP"
        : null;
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        getDocValue,
        defaultCurrency: "USD",
      })
    ).toBe("GBP");
  });

  it("resolves the cross-record link docname from the row first", () => {
    const getDocValue = (_dt: string, name: string) =>
      name === "RowCo" ? "JPY" : "USD";
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        row: { company: "RowCo" },
        doc: { company: "DocCo" },
        getDocValue,
      })
    ).toBe("JPY");
  });

  it("uses the registered default reader when ctx omits getDocValue", () => {
    setDocValueReader((dt, name, field) =>
      dt === "Company" && name === "Acme" && field === "default_currency"
        ? "CHF"
        : null
    );
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        defaultCurrency: "USD",
      })
    ).toBe("CHF");
  });

  it("falls back to the default when the reader yields nothing (built-in, headless)", () => {
    // No override + no `window` → built-in reader returns undefined → fallback.
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: { company: "Acme" },
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });

  it("falls back to the default when the cross-record link docname is missing", () => {
    setDocValueReader(() => "GBP");
    expect(
      resolveFieldCurrency("Company:company:default_currency", {
        doc: {},
        defaultCurrency: "USD",
      })
    ).toBe("USD");
  });
});

describe("doc-value reader seam", () => {
  it("returns the override when set, else the built-in", () => {
    const builtin = getDocValueReader();
    const stub = () => "USD";
    setDocValueReader(stub);
    expect(getDocValueReader()).toBe(stub);
    resetDocValueReader();
    expect(getDocValueReader()).toBe(builtin);
  });
});
