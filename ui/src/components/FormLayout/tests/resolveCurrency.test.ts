import { afterEach, describe, expect, it, vi } from "vitest";

// The built-in reader's one read. By default it never lands, so a resolution test
// that reaches the built-in reader sees "nothing yet" and falls back.
vi.mock("../../../api", () => ({
  listDocuments: vi.fn(() => new Promise(() => {})),
}));
import { listDocuments } from "../../../api";

/** Lets the read's two `.then` hops run. */
const flush = () => new Promise((resolve) => setTimeout(resolve));

import {
  resolveFieldCurrency,
  setDocValueReader,
  resetDocValueReader,
  getDocValueReader,
} from "../resolveCurrency";

afterEach(() => {
  resetDocValueReader();
  vi.clearAllMocks();
});

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

  it("falls back to the default while the built-in reader has nothing yet", () => {
    // No override → built-in reader, whose read has not landed → fallback.
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

  it("reads one field through the v2 list route once, then shares the value", async () => {
    let settle: (envelope: {
      data: Record<string, unknown>[];
    }) => void = () => {};
    vi.mocked(listDocuments).mockReturnValueOnce(
      new Promise((resolve) => (settle = resolve)) as never
    );
    const read = getDocValueReader();

    expect(read("Company", "Acme", "default_currency")).toBeUndefined();
    expect(read("Company", "Acme", "default_currency")).toBeUndefined();
    expect(listDocuments).toHaveBeenCalledTimes(1);
    expect(listDocuments).toHaveBeenCalledWith("Company", {
      fields: ["default_currency"],
      filters: { name: "Acme" },
      limit: 1,
    });

    settle({ data: [{ default_currency: "EUR" }] });
    await flush();
    expect(read("Company", "Acme", "default_currency")).toBe("EUR");
    expect(listDocuments).toHaveBeenCalledTimes(1);
  });

  it("forgets the oldest read past the cap", () => {
    const read = getDocValueReader();
    for (let i = 0; i <= 500; i++) read("Company", `C${i}`, "default_currency");
    expect(listDocuments).toHaveBeenCalledTimes(501);
    read("Company", "C0", "default_currency");
    expect(listDocuments).toHaveBeenCalledTimes(502);
    read("Company", "C2", "default_currency");
    expect(listDocuments).toHaveBeenCalledTimes(502);
  });

  it("answers null after a failed read and does not read again", async () => {
    vi.mocked(listDocuments).mockRejectedValueOnce(new Error("403"));
    const read = getDocValueReader();
    read("Company", "Secret", "default_currency");
    await flush();
    expect(read("Company", "Secret", "default_currency")).toBeNull();
    expect(listDocuments).toHaveBeenCalledTimes(1);
  });

  it("answers null for a record the route does not return", async () => {
    vi.mocked(listDocuments).mockResolvedValueOnce({ data: [] } as never);
    const read = getDocValueReader();
    read("Company", "Gone", "default_currency");
    await flush();
    expect(read("Company", "Gone", "default_currency")).toBeNull();
  });
});
